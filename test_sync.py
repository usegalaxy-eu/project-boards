import unittest

import yaml

from sync import plan_card, route

with open("boards.yml") as f:
    CFG = yaml.safe_load(f)
DEV = next(b for b in CFG["boards"] if b["name"] == "Dev Tasks")


def pr(draft=False, status=None, archived=False, on_board=True):
    items = [{"id": "I", "isArchived": archived, "project": {"id": "P"}, "status": status and {"name": status}}]
    return {"__typename": "PullRequest", "isDraft": draft, "projectItems": {"nodes": items if on_board else []}}


class Route(unittest.TestCase):
    def board(self, repo):
        b = route(repo, CFG)
        return b and b["name"]

    def test_routing(self):
        self.assertEqual(self.board("galaxyproject/galaxy"), "Dev Tasks")
        self.assertEqual(self.board("jmchilton/galaxy-tool-util-ts"), "Dev Tasks")
        self.assertEqual(self.board("usegalaxy-eu/infrastructure-playbook"), "Admin Tasks")
        self.assertEqual(self.board("bgruening/galaxytools"), "Tools")  # claimed by Tools, not Dev
        self.assertIsNone(self.board("galaxyproject/tools-iuc"))  # SIG board handles it
        self.assertIsNone(self.board("usegalaxy-eu/issues"))
        self.assertIsNone(self.board("arash77/galaxy-social-main"))  # personal fork
        self.assertIsNone(self.board("A4F-Tech/soac"))


class Plan(unittest.TestCase):
    def test_new_cards(self):
        self.assertEqual(plan_card(pr(draft=True, on_board=False), DEV, "P"), (True, "In progress"))
        self.assertEqual(plan_card(pr(on_board=False), DEV, "P"), (True, "In review"))
        issue = {"__typename": "Issue", "projectItems": {"nodes": []}}
        self.assertEqual(plan_card(issue, DEV, "P"), (True, None))

    def test_moves_only_from_allowed_statuses(self):
        self.assertEqual(plan_card(pr(status="🗂️ Backlog"), DEV, "P"), (False, "In review"))
        self.assertEqual(plan_card(pr(status="👨🏻‍💻 In progress"), DEV, "P"), (False, "In review"))
        self.assertEqual(plan_card(pr(status=None), DEV, "P"), (False, "In review"))
        self.assertEqual(plan_card(pr(status="⛔️ Blocked"), DEV, "P"), (False, None))
        self.assertEqual(plan_card(pr(status="✅ Done"), DEV, "P"), (False, None))
        self.assertEqual(plan_card(pr(draft=True, status="👀 In review"), DEV, "P"), (False, None))  # never backwards

    def test_leaves_archived_and_correct_cards_alone(self):
        self.assertEqual(plan_card(pr(archived=True), DEV, "P"), (False, None))
        self.assertEqual(plan_card(pr(status="👀 In review"), DEV, "P"), (False, None))

    def test_add_only_board_never_moves(self):
        self.assertEqual(plan_card(pr(status="🗂️ Backlog"), dict(DEV, mode="add"), "P"), (False, None))


if __name__ == "__main__":
    unittest.main()
