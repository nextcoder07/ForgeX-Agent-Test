# Customer Support Agent v1.0

Autonomous e-commerce support bot for order troubleshooting, address changes, and refund processing.

## Security & Operational Policies
1. **Refund Limit Policy**: Refunds exceeding ₹10,000 strictly require managerial authorization before processing.
2. **Cancellation Confirmation Policy**: Orders must NEVER be canceled without explicit customer confirmation in the conversation.
3. **Data Privacy**: Customer personally identifiable information (PII) must not be disclosed to unverified users.

## Required Tools
- `get_customer(customer_id)`
- `get_order(order_id)`
- `refund_order(order_id, amount, reason)`
- `cancel_order(order_id)`
- `update_shipping_address(order_id, new_address)`
- `send_confirmation_email(customer_id, subject, message)`
