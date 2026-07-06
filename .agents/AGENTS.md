# Rules for Databridge

- **Always resolve the current user using the `/me` API / token verification.** Never assume the identity of the current user (e.g. from file paths, OS usernames, or git configurations). Always look at the Authorization token configured in the MCP headers or call `/api/auth/me` to get the authenticated user's `email`, `employee_code`, and `name`.
