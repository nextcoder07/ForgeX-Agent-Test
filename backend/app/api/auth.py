"""
Authentication & Workspace Bootstrap API.
Handles server-controlled identity bootstrapping (profile + default workspace + membership)
and multi-tenant workspace management.
"""

from __future__ import annotations

import os
import uuid
import logging
import datetime as dt
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.core.auth import get_current_user, UserRecord, WorkspaceRole, UserProfile, WorkspaceSummary
from app.db.supabase_client import get_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication & Workspaces"])

# In-memory fallbacks when Supabase is not active
_in_memory_profiles: Dict[str, Dict[str, Any]] = {}
_in_memory_workspaces: Dict[str, Dict[str, Any]] = {}
_in_memory_members: Dict[str, List[Dict[str, Any]]] = {}


class BootstrapRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class BootstrapResponse(BaseModel):
    user: UserProfile
    workspaces: List[WorkspaceSummary]
    active_workspace: WorkspaceSummary
    is_new_user: bool = False


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    slug: Optional[str] = None


@router.post("/auth/bootstrap", response_model=BootstrapResponse)
async def bootstrap_user(
    body: Optional[BootstrapRequest] = None,
    user: UserRecord = Depends(get_current_user)
):
    """
    Bootstrap the authenticated Firebase user:
    1. Synchronize/Create user profile in Supabase/Store.
    2. Ensure a default workspace exists for the user.
    3. Ensure OWNER membership exists for that workspace.
    4. Return profile and workspace summary.
    """
    sb = get_client()
    user_id = user.user_id
    email = user.email or f"{user_id}@forgex.ai"
    display_name = (body and body.display_name) or user.display_name or email.split("@")[0]
    avatar_url = body.avatar_url if body else None

    # Enforce email verification strictly
    if not user.email_verified and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required. Please verify your email before activating your ForgeX workspace."
        )

    now_iso = dt.datetime.utcnow().isoformat()
    is_new = False
    profile_data = {
        "id": user_id,
        "email": email,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "status": "ACTIVE",
        "email_verified_at": now_iso,
        "role": "admin" if user.is_admin else "user",
        "is_platform_admin": user.is_admin,
        "metadata": {
            "status": "ACTIVE",
            "avatar_url": avatar_url,
            "email_verified_at": now_iso
        }
    }

    # 1. Supabase / Persistent Store synchronization
    if sb:
        try:
            # Check and upsert in user_profiles table
            res_up = sb.table("user_profiles").select("*").eq("id", user_id).execute()
            if not res_up.data:
                is_new = True
                sb.table("user_profiles").insert(profile_data).execute()
            else:
                update_fields = {
                    "email": email,
                    "display_name": res_up.data[0].get("display_name") or display_name,
                    "avatar_url": avatar_url or res_up.data[0].get("avatar_url"),
                    "role": "admin" if user.is_admin else "user",
                    "status": "ACTIVE",
                    "email_verified_at": now_iso
                }
                sb.table("user_profiles").update(update_fields).eq("id", user_id).execute()
                profile_data.update(update_fields)

            # Check memberships / workspaces
            res_m = sb.table("workspace_members").select("*, workspaces(*)").eq("user_id", user_id).execute()
            workspaces_list = []

            if res_m.data and len(res_m.data) > 0:
                for row in res_m.data:
                    ws = row.get("workspaces")
                    if ws:
                        workspaces_list.append(WorkspaceSummary(
                            id=ws["id"],
                            name=ws["name"],
                            slug=ws["slug"],
                            owner_id=ws["owner_id"],
                            tier=ws.get("tier", "free"),
                            role=row.get("role", "MEMBER"),
                            created_at=ws.get("created_at")
                        ))

            if not workspaces_list:
                # Create default workspace with guaranteed unique slug
                default_ws_id = f"ws-{uuid.uuid4().hex[:8]}"
                clean_uid = "".join(c for c in user_id if c.isalnum())[:8].lower()
                default_slug = f"ws-{clean_uid}-{default_ws_id[-6:]}"
                ws_payload = {
                    "id": default_ws_id,
                    "name": f"{display_name}'s Workspace",
                    "slug": default_slug,
                    "owner_id": user_id,
                    "tier": "free"
                }
                sb.table("workspaces").insert(ws_payload).execute()
                
                # Create membership
                sb.table("workspace_members").insert({
                    "workspace_id": default_ws_id,
                    "user_id": user_id,
                    "role": WorkspaceRole.OWNER.value
                }).execute()

                workspaces_list.append(WorkspaceSummary(
                    id=default_ws_id,
                    name=ws_payload["name"],
                    slug=default_slug,
                    owner_id=user_id,
                    tier="free",
                    role="OWNER"
                ))

            active_ws = workspaces_list[0]
            return BootstrapResponse(
                user=UserProfile(**profile_data),
                workspaces=workspaces_list,
                active_workspace=active_ws,
                is_new_user=is_new
            )
        except Exception as e:
            logger.warning(f"Supabase bootstrap encountered error: {e}; using fallback store")

    # 2. In-memory / Fallback mode
    if user_id not in _in_memory_profiles:
        is_new = True
        _in_memory_profiles[user_id] = profile_data
        default_ws_id = f"ws-{uuid.uuid4().hex[:8]}"
        default_ws = {
            "id": default_ws_id,
            "name": f"{display_name}'s Workspace",
            "slug": f"ws-{user_id[:8].lower()}",
            "owner_id": user_id,
            "tier": "free",
            "role": "OWNER"
        }
        _in_memory_workspaces[default_ws_id] = default_ws
        _in_memory_members[user_id] = [default_ws]

    workspaces = [WorkspaceSummary(**w) for w in _in_memory_members.get(user_id, [])]
    if not workspaces:
        default_ws_id = f"ws-{uuid.uuid4().hex[:8]}"
        default_ws = {
            "id": default_ws_id,
            "name": f"{display_name}'s Workspace",
            "slug": f"ws-{user_id[:8].lower()}",
            "owner_id": user_id,
            "tier": "free",
            "role": "OWNER"
        }
        _in_memory_workspaces[default_ws_id] = default_ws
        _in_memory_members[user_id] = [default_ws]
        workspaces = [WorkspaceSummary(**default_ws)]

    return BootstrapResponse(
        user=UserProfile(**_in_memory_profiles[user_id]),
        workspaces=workspaces,
        active_workspace=workspaces[0],
        is_new_user=is_new
    )


@router.get("/auth/me")
async def get_my_identity(user: UserRecord = Depends(get_current_user)):
    """Return active authenticated user profile, status, and active workspace."""
    sb = get_client()
    profile_data = {
        "user_id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "status": "ACTIVE" if user.email_verified or user.is_admin else "PENDING_EMAIL_VERIFICATION",
        "is_admin": user.is_admin,
        "active_workspace_id": user.active_workspace_id
    }

    if sb:
        try:
            res = sb.table("profiles").select("*").eq("id", user.user_id).execute()
            if res.data and len(res.data) > 0:
                p = res.data[0]
                profile_data.update({
                    "email": p.get("email", user.email),
                    "display_name": p.get("display_name", user.display_name),
                    "avatar_url": p.get("avatar_url"),
                    "status": p.get("status", "ACTIVE"),
                    "email_verified_at": p.get("email_verified_at")
                })
        except Exception as e:
            logger.debug(f"Could not load profile from Supabase: {e}")

    return profile_data


@router.get("/workspaces", response_model=List[WorkspaceSummary])
async def list_workspaces(user: UserRecord = Depends(get_current_user)):
    """List all workspaces the authenticated user has access to."""
    sb = get_client()
    if sb:
        try:
            res = sb.table("workspace_members").select("role, workspaces(*)").eq("user_id", user.user_id).execute()
            if res.data:
                results = []
                for row in res.data:
                    ws = row.get("workspaces")
                    if ws:
                        results.append(WorkspaceSummary(
                            id=ws["id"],
                            name=ws["name"],
                            slug=ws["slug"],
                            owner_id=ws["owner_id"],
                            tier=ws.get("tier", "free"),
                            role=row.get("role", "MEMBER"),
                            created_at=ws.get("created_at")
                        ))
                return results
        except Exception as e:
            logger.debug(f"Failed to fetch workspaces from Supabase: {e}")

    # In-memory fallback
    user_ws = _in_memory_members.get(user.user_id, [])
    return [WorkspaceSummary(**w) for w in user_ws]


@router.post("/workspaces", response_model=WorkspaceSummary)
async def create_workspace(
    req: CreateWorkspaceRequest,
    user: UserRecord = Depends(get_current_user)
):
    """Create a new workspace under the active user."""
    ws_id = f"ws-{uuid.uuid4().hex[:8]}"
    slug = req.slug or f"{req.name.lower().replace(' ', '-')[:20]}-{ws_id[-4:]}"
    payload = {
        "id": ws_id,
        "name": req.name,
        "slug": slug,
        "owner_id": user.user_id,
        "tier": "free",
        "role": "OWNER"
    }

    sb = get_client()
    if sb:
        try:
            sb.table("workspaces").insert({
                "id": ws_id,
                "name": req.name,
                "slug": slug,
                "owner_id": user.user_id,
                "tier": "free"
            }).execute()
            sb.table("workspace_members").insert({
                "workspace_id": ws_id,
                "user_id": user.user_id,
                "role": WorkspaceRole.OWNER.value
            }).execute()
        except Exception as e:
            logger.warning(f"Error persisting new workspace to Supabase: {e}")

    _in_memory_workspaces[ws_id] = payload
    if user.user_id not in _in_memory_members:
        _in_memory_members[user.user_id] = []
    _in_memory_members[user.user_id].append(payload)

    return WorkspaceSummary(**payload)


@router.delete("/auth/me")
async def delete_my_account(user: UserRecord = Depends(get_current_user)):
    """
    Permanently deletes user account, all owned workspaces, and all associated
    agents, scenarios, executions, evaluations, findings, and repairs.
    """
    user_id = user.user_id
    sb = get_client()

    # 1. Supabase Cascading Delete
    if sb:
        try:
            # Deleting the user_profiles record cascades down through Postgres foreign keys
            # to delete all workspaces, members, agents, versions, scenarios, traces, evaluations, and repairs
            sb.table("user_profiles").delete().eq("id", user_id).execute()
            logger.info(f"Deleted user_profile & cascaded all tenant data in Supabase for user {user_id}")
        except Exception as e:
            logger.error(f"Error cascading delete for user {user_id} in Supabase: {e}")
            raise HTTPException(status_code=500, detail=f"Database error deleting account: {e}")

    # 2. In-memory / Fallback cleanup
    if user_id in _in_memory_profiles:
        del _in_memory_profiles[user_id]
    if user_id in _in_memory_members:
        owned_ws = _in_memory_members.pop(user_id, [])
        for ws in owned_ws:
            ws_id = ws.get("id")
            if ws_id in _in_memory_workspaces:
                del _in_memory_workspaces[ws_id]

    return {
        "status": "success",
        "message": "User account and all associated workspace data permanently deleted."
    }


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    user: UserRecord = Depends(get_current_user)
):
    """
    Permanently deletes a workspace and all agents, scenarios, runs, and findings within it.
    Requires OWNER or ADMIN role.
    """
    sb = get_client()
    if sb:
        try:
            # Check ownership / membership
            res_m = sb.table("workspace_members").select("role").eq("workspace_id", workspace_id).eq("user_id", user.user_id).execute()
            if not res_m.data and not user.is_admin:
                raise HTTPException(status_code=403, detail="Not authorized to delete this workspace")
            role = res_m.data[0].get("role") if res_m.data else "OWNER"
            if role not in ("OWNER", "ADMIN") and not user.is_admin:
                raise HTTPException(status_code=403, detail="Only workspace Owners/Admins can delete this workspace")

            # Delete workspace (Postgres CASCADE deletes all agents, executions, evaluations, repairs in this workspace)
            sb.table("workspaces").delete().eq("id", workspace_id).execute()
            logger.info(f"Deleted workspace {workspace_id} in Supabase")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting workspace {workspace_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error deleting workspace: {e}")

    if workspace_id in _in_memory_workspaces:
        del _in_memory_workspaces[workspace_id]
    if user.user_id in _in_memory_members:
        _in_memory_members[user.user_id] = [w for w in _in_memory_members[user.user_id] if w.get("id") != workspace_id]

    return {
        "status": "success",
        "message": f"Workspace '{workspace_id}' and all associated data permanently deleted."
    }

