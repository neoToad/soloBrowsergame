from ...models.combat import CombatEncounter
from ...models.world import Choice, Quest, Scene
from .shared import (
    CANVAS_PADDING,
    CARD_HEIGHT,
    CARD_WIDTH,
    GRID_START_X,
    GRID_START_Y,
    GRID_X_GAP,
    GRID_Y_GAP,
    PARALLEL_ARROW_SPACING,
)


def build_canvas_data(quest_id):
    quest = Quest.objects.get(pk=quest_id)
    scenes_qs = quest.scenes.only(
        "id", "canvas_x", "canvas_y", "scene_type", "key", "title", "requires_roll", "ending_type"
    )

    scenes = []
    scene_ids = []
    scene_roll_lookup = {}
    scene_lookup = {}
    for index, s in enumerate(scenes_qs):
        display_x = s.canvas_x
        display_y = s.canvas_y
        if s.canvas_x == 0 and s.canvas_y == 0:
            display_x = GRID_START_X + (index % 4) * GRID_X_GAP
            display_y = GRID_START_Y + (index // 4) * GRID_Y_GAP

        scene_data = {
            "id": s.id,
            "canvas_x": display_x,
            "canvas_y": display_y,
            "scene_type": s.scene_type,
            "key": s.key,
            "title": s.title,
            "requires_roll": s.requires_roll,
            "ending_type": s.ending_type,
        }
        scenes.append(scene_data)
        scene_ids.append(s.id)
        scene_roll_lookup[s.id] = s.requires_roll
        scene_lookup[s.id] = scene_data

    choices_qs = Choice.objects.filter(scene_id__in=scene_ids).only(
        "id", "scene_id", "label", "target_scene_id", "success_scene_id", "failure_scene_id"
    )
    encounters_qs = CombatEncounter.objects.filter(scene_id__in=scene_ids).select_related(
        "enemy", "victory_scene", "defeat_scene"
    ).only("id", "scene_id", "enemy_id", "victory_scene_id", "defeat_scene_id")

    choices = []
    arrows = []
    for c in choices_qs:
        choice_data = {
            "id": c.id,
            "source_scene_id": c.scene_id,
            "source_requires_roll": scene_roll_lookup.get(c.scene_id, False),
            "label": c.label,
            "target_scene_id": c.target_scene_id,
            "success_scene_id": c.success_scene_id,
            "failure_scene_id": c.failure_scene_id,
        }
        choices.append(choice_data)
        source_scene = scene_lookup.get(c.scene_id)
        if not source_scene:
            continue

        source_x = source_scene["canvas_x"] + CARD_WIDTH
        source_y = source_scene["canvas_y"] + (CARD_HEIGHT // 2)

        def append_arrow(target_scene_id, kind, choice_id=c.id):
            if not target_scene_id:
                return
            target_scene = scene_lookup.get(target_scene_id)
            if not target_scene:
                return
            target_x = target_scene["canvas_x"]
            target_y = target_scene["canvas_y"] + (CARD_HEIGHT // 2)
            arrows.append({
                "id": f"choice-{choice_id}-{kind}",
                "choice_id": choice_id,
                "kind": kind,
                "label": c.label,
                "source_scene_id": c.scene_id,
                "target_scene_id": target_scene_id,
                "success_scene_id": target_scene_id if kind == "success" else None,
                "failure_scene_id": target_scene_id if kind == "failure" else None,
                "x1": source_x,
                "y1": source_y,
                "x2": target_x,
                "y2": target_y,
                "label_x": (source_x + target_x) // 2,
                "label_y": ((source_y + target_y) // 2) - 6,
            })

        if choice_data["source_requires_roll"]:
            append_arrow(c.success_scene_id, "success")
            append_arrow(c.failure_scene_id, "failure")
        else:
            append_arrow(c.target_scene_id, "direct")

    for encounter in encounters_qs:
        source_scene = scene_lookup.get(encounter.scene_id)
        if not source_scene:
            continue

        source_x = source_scene["canvas_x"] + CARD_WIDTH
        source_y = source_scene["canvas_y"] + (CARD_HEIGHT // 2)

        def append_combat_arrow(target_scene_id, kind, label):
            if not target_scene_id:
                return
            target_scene = scene_lookup.get(target_scene_id)
            if not target_scene:
                return
            target_x = target_scene["canvas_x"]
            target_y = target_scene["canvas_y"] + (CARD_HEIGHT // 2)
            arrows.append({
                "id": f"combat-{encounter.id}-{kind}",
                "choice_id": None,
                "kind": kind,
                "label": label,
                "source_scene_id": encounter.scene_id,
                "target_scene_id": target_scene_id,
                "success_scene_id": target_scene_id if kind == "success" else None,
                "failure_scene_id": target_scene_id if kind == "failure" else None,
                "x1": source_x,
                "y1": source_y,
                "x2": target_x,
                "y2": target_y,
                "label_x": (source_x + target_x) // 2,
                "label_y": ((source_y + target_y) // 2) - 6,
            })

        append_combat_arrow(encounter.victory_scene_id, "success", "WIN")
        append_combat_arrow(encounter.defeat_scene_id, "failure", "LOSE")

    arrows_by_edge = {}
    for arrow in arrows:
        edge_key = (arrow.get("source_scene_id"), arrow.get("target_scene_id"))
        arrows_by_edge.setdefault(edge_key, []).append(arrow)

    for grouped_arrows in arrows_by_edge.values():
        total = len(grouped_arrows)
        center_index = (total - 1) / 2
        for index, arrow in enumerate(grouped_arrows):
            lane = index - center_index
            offset = int(lane * PARALLEL_ARROW_SPACING)
            arrow["offset_index"] = index
            arrow["offset_total"] = total
            arrow["offset_px"] = offset
            arrow["y1"] += offset
            arrow["y2"] += offset
            arrow["label_y"] += offset

    external_ending_targets: dict[int, list[tuple[int, str]]] = {}
    for c_data in choices:
        source = scene_lookup.get(c_data["source_scene_id"])
        tid = c_data["target_scene_id"]
        if source and source["scene_type"] == "ending" and tid and tid not in scene_lookup:
            external_ending_targets.setdefault(tid, []).append((c_data["source_scene_id"], c_data["label"]))

    if external_ending_targets:
        hub_map = {
            s.id: s
            for s in Scene.objects.filter(pk__in=external_ending_targets.keys(), scene_type="hub").only(
                "id", "key", "title"
            )
        }
        for target_id, source_list in external_ending_targets.items():
            if target_id not in hub_map:
                continue
            hub = hub_map[target_id]
            for source_scene_id, label in source_list:
                source = scene_lookup.get(source_scene_id)
                if not source:
                    continue
                source.setdefault("hub_exits", []).append({
                    "hub_key": hub.key,
                    "hub_title": hub.title,
                    "choice_label": label,
                })

    if scenes:
        max_scene_x = max(scene["canvas_x"] for scene in scenes)
        max_scene_y = max(scene["canvas_y"] for scene in scenes)
        canvas_width = max_scene_x + CARD_WIDTH + CANVAS_PADDING
        canvas_height = max_scene_y + CARD_HEIGHT + CANVAS_PADDING
    else:
        canvas_width = GRID_START_X + CARD_WIDTH + CANVAS_PADDING
        canvas_height = GRID_START_Y + CARD_HEIGHT + CANVAS_PADDING

    return {
        "quest": quest,
        "scenes": scenes,
        "choices": choices,
        "arrows": arrows,
        "canvas_width": canvas_width,
        "canvas_height": canvas_height,
    }


class QuestCanvasRenderer:
    @staticmethod
    def build(quest_id):
        return build_canvas_data(quest_id)


def get_canvas_data(quest_id):
    return QuestCanvasRenderer.build(quest_id)


def get_scene_hub_exits(scene_id, quest_id):
    quest_scene_ids = set(Scene.objects.filter(quest_id=quest_id).values_list("id", flat=True))
    choices = list(Choice.objects.filter(scene_id=scene_id).only("id", "label", "target_scene_id"))
    external_ids = [c.target_scene_id for c in choices if c.target_scene_id and c.target_scene_id not in quest_scene_ids]
    if not external_ids:
        return []
    hub_map = {
        s.id: s for s in Scene.objects.filter(pk__in=external_ids, scene_type="hub").only("id", "key", "title")
    }
    return [
        {"hub_key": hub_map[c.target_scene_id].key, "hub_title": hub_map[c.target_scene_id].title, "choice_label": c.label}
        for c in choices
        if c.target_scene_id in hub_map
    ]


class QuestHubExitResolver:
    @staticmethod
    def resolve(scene_id, quest_id):
        return get_scene_hub_exits(scene_id, quest_id)
