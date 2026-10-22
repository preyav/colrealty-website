"""Visibility rules shared by editor layout and validation."""
from .text_feature_choices import decode_features
FEATURE_PAIRS = [('fireplaces', 'fireplace_features_types'), ('has_pool', 'pool_features_types'), ('waterfront_features', 'water_body_name'), ('solar', 'solar_ownership'), ('spa', 'spa_features_types')]
def dependent_visible(name, data):
    if name == 'fireplace_features_types':
        value = data.get('fireplaces')
        try:
            return value not in (None, '') and int(value) > 0
        except (ValueError, TypeError):
            return False
    controller = {'pool_features_types': 'has_pool', 'solar_ownership': 'solar', 'spa_features_types': 'spa', 'move_in_special_description': 'move_in_special_yn'}.get(name)
    if controller:
        return data.get(controller) in (True, 'true', 'True', 'yes', 'Yes')
    if name == 'water_body_name':
        selected = decode_features(data.get('waterfront_features'))
        return bool(selected) and 'none' not in selected
    return True
