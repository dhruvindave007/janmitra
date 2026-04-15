"""
Custom Django Admin Site for JanMitra Command Center.

Provides:
- Branded header/title
- Grouped model index (5 operational groups + 1 system group)
- Hidden legacy/system models from index
"""

from collections import OrderedDict
from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig


# ── Model grouping configuration ──────────────────────────────────────────────
# Maps (app_label, model_name) → group key.
# Models not listed here are placed in the "System & Audit" fallback group.

GROUPS = OrderedDict([
    ('user_management', {
        'label': '🔐 User Management',
        'models': [
            ('authentication', 'user'),
            ('authentication', 'authorityprofile'),
        ],
    }),
    ('police_infra', {
        'label': '🏢 Police Infrastructure',
        'models': [
            ('core', 'policestation'),
        ],
    }),
    ('case_management', {
        'label': '📁 Case Management',
        'models': [
            ('reports', 'case'),
            ('reports', 'incident'),
            ('reports', 'escalationhistory'),
            ('reports', 'casestatushistory'),
            ('reports', 'incidentmedia'),
        ],
    }),
    ('investigation', {
        'label': '💬 Investigation',
        'models': [
            ('reports', 'investigationmessage'),
            ('reports', 'casenote'),
        ],
    }),
    ('notifications', {
        'label': '🔔 Notifications',
        'models': [
            ('notifications', 'notification'),
        ],
    }),
    ('system', {
        'label': '📋 System & Audit',
        'models': [
            ('audit', 'auditlog'),
            ('audit', 'identityreveallog'),
            ('core', 'appversionconfig'),
        ],
    }),
])

# Models to completely hide from the admin index page.
# They remain accessible via direct URL for superusers.
HIDDEN_MODELS = {
    # Legacy report system — superseded by Case workflow
    ('reports', 'report'),
    ('reports', 'reportstatushistory'),
    ('reports', 'reportnote'),
    # System-managed — no manual admin interaction needed
    ('authentication', 'devicesession'),
    ('authentication', 'invitecode'),
    ('authentication', 'janmitraprofile'),
    ('token_blacklist', 'blacklistedtoken'),
    ('token_blacklist', 'outstandingtoken'),
    # Legacy escalation models — superseded by EscalationHistory
    ('escalation', 'escalation'),
    ('escalation', 'identityrevealrequest'),
    ('escalation', 'decryptionrequest'),
    # Legacy media storage — superseded by IncidentMedia
    ('media_storage', 'reportmedia'),
    ('media_storage', 'mediaaccesslog'),
}

# Build reverse lookup: (app_label, model_name) → group_key
_MODEL_TO_GROUP = {}
for _gk, _gv in GROUPS.items():
    for _pair in _gv['models']:
        _MODEL_TO_GROUP[_pair] = _gk


class JanMitraAdminSite(AdminSite):
    """Custom admin site with branded header and grouped model index."""

    site_header = 'JanMitra Command Center'
    site_title = 'JanMitra Admin'
    index_title = 'Operations Dashboard'

    def get_app_list(self, request, app_label=None):
        """
        Override to group models into operational sections
        instead of Django's default per-app grouping.
        """
        original = super().get_app_list(request, app_label=app_label)

        # If viewing a single app's page, return default behaviour
        if app_label:
            return original

        # Collect every model entry from the original list
        model_lookup = {}  # (app_label, model_name) → model_dict
        for app in original:
            for model in app['models']:
                key = (app['app_label'], model['object_name'].lower())
                model_lookup[key] = model

        # Build grouped app list
        grouped = []
        for group_key, group_cfg in GROUPS.items():
            models_in_group = []
            for pair in group_cfg['models']:
                if pair in model_lookup and pair not in HIDDEN_MODELS:
                    models_in_group.append(model_lookup[pair])

            if models_in_group:
                grouped.append({
                    'name': group_cfg['label'],
                    'app_label': group_key,
                    'app_url': '',
                    'has_module_perms': True,
                    'models': models_in_group,
                })

        # Any remaining models not in GROUPS and not hidden → "Other" group
        assigned = set()
        for pairs in [g['models'] for g in GROUPS.values()]:
            assigned.update(pairs)

        other_models = []
        for key, model in model_lookup.items():
            if key not in assigned and key not in HIDDEN_MODELS:
                other_models.append(model)

        if other_models:
            grouped.append({
                'name': '⚙️ Other',
                'app_label': 'other',
                'app_url': '',
                'has_module_perms': True,
                'models': other_models,
            })

        return grouped


class JanMitraAdminConfig(AdminConfig):
    """Replace django.contrib.admin to wire our custom AdminSite."""
    default_site = 'janmitra_backend.admin_site.JanMitraAdminSite'
