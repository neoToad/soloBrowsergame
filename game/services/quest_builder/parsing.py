class QuestFormParser:
    @staticmethod
    def parse_scene_form(data):
        requires_roll = str(data.get("requires_roll", "")).lower() in ("1", "true", "on", "yes")
        raw_dc = str(data.get("roll_difficulty") or "").strip()
        raw_item = str(data.get("consume_item_id") or "").strip()
        return {
            "title": (data.get("title") or "").strip(),
            "key": (data.get("key") or "").strip(),
            "description": (data.get("description") or "").strip(),
            "scene_type": (data.get("scene_type") or "normal").strip() or "normal",
            "ending_type": (data.get("ending_type") or "").strip(),
            "requires_roll": requires_roll,
            "roll_stat": (data.get("roll_stat") or "").strip(),
            "roll_difficulty": int(raw_dc) if raw_dc else 12,
            "consume_item_id": int(raw_item) if raw_item else None,
            "cash_change": int(data.get("cash_change") or 0),
            "rep_change": int(data.get("rep_change") or 0),
            "heat_change": int(data.get("heat_change") or 0),
            "receive_property_id": int(data.get("receive_property_id") or 0) or None,
            "lose_property_id": int(data.get("lose_property_id") or 0) or None,
            "receive_territory_id": int(data.get("receive_territory_id") or 0) or None,
            "lose_territory_id": int(data.get("lose_territory_id") or 0) or None,
            "discover_territory_id": int(data.get("discover_territory_id") or 0) or None,
        }

    @staticmethod
    def parse_choice_form(data):
        routing_type = (data.get("routing_type") or "direct").strip()
        if routing_type == "roll":
            raw_success = str(data.get("success_scene") or "").strip()
            raw_failure = str(data.get("failure_scene") or "").strip()
            target_scene_id = None
            success_scene_id = int(raw_success) if raw_success else None
            failure_scene_id = int(raw_failure) if raw_failure else None
        else:
            raw_target = str(data.get("target_scene") or "").strip()
            target_scene_id = int(raw_target) if raw_target else None
            success_scene_id = None
            failure_scene_id = None
        return {
            "label": (data.get("label") or "").strip(),
            "routing_type": routing_type,
            "target_scene_id": target_scene_id,
            "success_scene_id": success_scene_id,
            "failure_scene_id": failure_scene_id,
            "set_flag_name": (data.get("set_flag_name") or "").strip(),
            "clear_flag_name": (data.get("clear_flag_name") or "").strip(),
            "arrival_flavor": (data.get("arrival_flavor") or "").strip(),
            "failure_arrival_flavor": (data.get("failure_arrival_flavor") or "").strip(),
        }

    @staticmethod
    def parse_combat_form(data):
        raw_enemy = str(data.get("enemy_id") or "").strip()
        if not raw_enemy:
            return None
        raw_victory = str(data.get("victory_scene_id") or "").strip()
        raw_defeat = str(data.get("defeat_scene_id") or "").strip()
        return {
            "enemy_id": int(raw_enemy),
            "victory_scene_id": int(raw_victory) if raw_victory else None,
            "defeat_scene_id": int(raw_defeat) if raw_defeat else None,
            "victory_arrival_flavor": (data.get("victory_arrival_flavor") or "").strip(),
            "defeat_arrival_flavor": (data.get("defeat_arrival_flavor") or "").strip(),
        }


def parse_scene_form(data):
    return QuestFormParser.parse_scene_form(data)


def parse_choice_form(data):
    return QuestFormParser.parse_choice_form(data)


def parse_combat_form(data):
    return QuestFormParser.parse_combat_form(data)
