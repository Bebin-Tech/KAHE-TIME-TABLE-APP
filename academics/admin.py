"""Academic mutations use the scoped application API and scheduling lock.

Do not register these models in Django admin: generic admin saves would bypass
the published-schedule validation and application audit service.
"""
