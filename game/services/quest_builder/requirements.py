from django.db import transaction


def build_requirement_groups_from_post(obj, post_data):
    from ...models.requirements import Requirement, RequirementGroup

    with transaction.atomic():
        old_groups = list(obj.requirements.all())
        obj.requirements.clear()
        for group in old_groups:
            if not group.gated_choices.exists() and not group.gated_quests.exists():
                for req in group.requirements.all():
                    if not req.groups.exists():
                        req.delete()
                group.delete()

        raw_count = str(post_data.get("group_count") or "").strip()
        try:
            group_count = int(raw_count)
        except (ValueError, TypeError):
            return []

        created_groups = []
        for gi in range(group_count):
            logic = (post_data.get(f"group_{gi}_logic") or "all").strip()
            if logic not in ("all", "any"):
                logic = "all"

            raw_req_count = str(post_data.get(f"group_{gi}_req_count") or "").strip()
            try:
                req_count = int(raw_req_count)
            except (ValueError, TypeError):
                req_count = 0

            group = RequirementGroup.objects.create(label=f"Group {gi + 1}", logic=logic)

            for ri in range(req_count):
                ctype = (post_data.get(f"group_{gi}_req_{ri}_type") or "").strip()
                if not ctype:
                    continue
                param = (post_data.get(f"group_{gi}_req_{ri}_param") or "").strip()
                param2 = (post_data.get(f"group_{gi}_req_{ri}_param2") or "").strip()

                req_kwargs = {"condition_type": ctype}
                if ctype in ("stat_gte", "stat_lte"):
                    if ":" in param:
                        stat_name, _, raw_val = param.partition(":")
                        req_kwargs["stat_name"] = stat_name.strip()
                        try:
                            req_kwargs["stat_value"] = int(raw_val.strip())
                        except ValueError:
                            req_kwargs["stat_value"] = 0
                    else:
                        req_kwargs["stat_name"] = param
                        req_kwargs["stat_value"] = 0
                elif ctype in ("has_flag", "missing_flag"):
                    req_kwargs["flag_name"] = param
                elif ctype in ("quest_completed", "quest_not_done"):
                    if param:
                        try:
                            req_kwargs["required_quest_id"] = int(param)
                        except ValueError:
                            pass
                elif ctype == "quest_ending":
                    if param:
                        try:
                            req_kwargs["required_quest_id"] = int(param)
                        except ValueError:
                            pass
                    if param2:
                        req_kwargs["required_ending_type"] = param2
                elif ctype in ("level_gte", "xp_gte"):
                    try:
                        req_kwargs["stat_value"] = int(param)
                    except (ValueError, TypeError):
                        req_kwargs["stat_value"] = 0
                elif ctype in ("has_item", "missing_item"):
                    if param:
                        try:
                            req_kwargs["required_item_id"] = int(param)
                        except ValueError:
                            pass
                elif ctype in ("has_contact", "missing_contact"):
                    if param:
                        try:
                            req_kwargs["required_contact_id"] = int(param)
                        except ValueError:
                            pass

                req, _ = Requirement.objects.get_or_create(**req_kwargs)
                group.requirements.add(req)

            obj.requirements.add(group)
            created_groups.append(group)

        return created_groups


class RequirementGroupBuilder:
    @staticmethod
    def build_from_post(obj, post_data):
        return build_requirement_groups_from_post(obj, post_data)
