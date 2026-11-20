"""The safety hooks (#27): the guard (PreToolUse on Bash), the PermissionRequest deny and the
PermissionDenied refusal log, fed hook-shaped stdin and judged by the decision they print and
the refusals they record (ADR 0007)."""
import json
import subprocess
import unittest

from tests.test_lifecycle import Working
from tests.test_shift import LEDGER, ROOT
from tests.test_stop import Stopping

S = "third-shift/20-widget-version-1"


class Hooks(Working):
    """Helpers, no tests."""

    def hook(self, cmd, event, session="s1", env=None, **fields):
        hook = {"session_id": session, "cwd": str(self.target), "hook_event_name": event, **fields}
        code, out = self.shift(cmd, input=json.dumps(hook), env=env)
        self.assertEqual(code, 0, out)
        return out

    def guard(self, command, **kw):
        return self.hook("guard", "PreToolUse", tool_name="Bash", tool_input={"command": command},
                         **kw)

    def refused_all(self, commands):
        for c in commands:
            with self.subTest(c):
                d = self.guard(c).get("hookSpecificOutput", {})
                self.assertEqual(d.get("permissionDecision"), "deny", c)
                self.assertEqual(d["hookEventName"], "PreToolUse")
                self.assertTrue(d["permissionDecisionReason"].strip())
        self.assertEqual([r["input"] for r in self.refusals()], commands)

    def refusals(self):
        """Refusals recorded in the ledger, or, off the shift branch, in runtime state."""
        f = self.home / "acme" / "widget" / "refusals.jsonl"
        return [json.loads(r) for r in f.read_text().splitlines()] if f.exists() else (
            self.ledger().get("refused", []))

    def allowed_all(self, commands, env=None):
        for c in commands:
            with self.subTest(c):
                self.assertEqual(self.guard(c, env=env), {}, c)
        self.assertEqual(self.refusals(), [])

    def prompt(self, tool="Bash", **kw):
        return self.hook("deny-prompt", "PermissionRequest", tool_name=tool,
                         tool_input={"command": "rm -rf build"}, **kw)


class Guard(Hooks):
    """An armed shift, #21 In progress, its session off the shift branch, so each refusal is
    recorded in runtime state (cheap) rather than committed and pushed (Recording)."""
    fixture = "admitted"

    def setUp(self):
        super().setUp()
        self.git("checkout", "-q", "-b", "side")

    def test_pushes_to_the_default_branch_or_any_branch_but_third_shift_are_refused(self):
        self.refused_all([
            "git push origin main", "git push origin HEAD:main", "git push origin HEAD:refs/heads/main",
            "git push", "git push origin", "git push origin HEAD", f"git push origin {S}:main",
            f"git push origin {S} main", "git push origin v1.0", f"git push origin {S}/../main",
            "git push -- origin main", f"git push origin {{main,{S}}}", "git push origin 'main'",
        ])

    def test_the_whole_command_is_read(self):
        self.refused_all([
            "git -C . push origin main", "git --git-dir=.git push origin main",
            "/usr/bin/git push origin main", "\\git push origin main", "g''it push origin main",
            "env FOO=1 git push origin main", "command git push origin main",
            "nice -n 5 timeout 9 git push origin main", "echo hi; git push origin main",
            "true && git push origin main", "false || git push origin main",
            "echo x | git push origin main", "(git push origin main)",
            "{ git push origin main; }", "if true; then git push origin main; fi",
            "echo $(git push origin main)", "echo `git push origin main`",
            'echo "$(git push origin main)"', "echo $(echo $(git push origin main))",
            "sh -c 'git push origin main'", 'bash -c "git status && git push origin main"',
            "eval git push origin main", "eval 'git push origin main'",
            "xargs git push origin <<< main", "echo main | xargs -I{} git push origin {}",
            "git push origin $BRANCH", "b=main; git push origin $b", f"$GIT push origin {S}",
            "git status\ngit push origin main", "git status # a comment\ngit push origin main",
            "echo a#b; git push origin main", "git status \\\n&& git push origin main",
            "python3 -c \"import os; os.system('git push origin main')\"",
            f"find . -exec git push origin main \\;", "cat <(git push origin main)",
        ])

    def test_force_delete_and_mirror_pushes_are_refused(self):
        self.refused_all([
            f"git push -f origin {S}", f"git push --force origin {S}",
            f"git push --force-with-lease origin {S}", f"git push --force-with-lease={S} origin {S}",
            f"git push --forc origin {S}", f"git push -uf origin {S}", f"git push origin +{S}",
            f"git push origin +HEAD:{S}", f"git push --force-if-includes origin {S}",
            f"git push --delete origin {S}", f"git push -d origin {S}", f"git push origin :{S}",
            "git push --mirror origin", "git push --all origin", f"git push --prune origin {S}",
            f"git push --tags origin {S}", f"git -c remote.origin.mirror=true push origin {S}",
            f"git -c alias.p=push p origin {S}",
        ])

    def test_branch_deletes_and_remote_changes_are_refused(self):
        self.refused_all([
            f"git branch -d {S}", "git branch -D old", "git branch --delete old",
            "git branch --del old", "git branch -rd origin/old", "git branch -r -D origin/old",
            "git update-ref -d refs/heads/main", "git remote add evil https://example.com/x.git",
            "git remote set-url origin https://example.com/x.git", "git remote remove origin",
            "git remote rm origin", "git remote rename origin x", "git remote prune origin",
            "git config remote.origin.url https://example.com/x.git",
            "git config --unset remote.origin.url", "git config alias.p push",
            "git config --global url.https://example.com/.insteadOf https://github.com/",
            "git config set remote.origin.pushurl x", "git config --edit",
            "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.mirror git status",
        ])

    def test_destructive_gh_commands_are_refused(self):
        self.refused_all([
            "gh repo delete acme/widget --yes", "gh repo edit --default-branch x",
            "gh repo archive", "gh repo rename x", "gh repo sync", "gh issue delete 21",
            "gh issue transfer 21 acme/other", "gh release delete v1", "gh pr merge 3",
            "gh label delete bug", "gh repo deploy-key delete 1", "gh -R acme/widget issue delete 5",
            "gh alias set x 'repo delete'", "gh api -X DELETE repos/acme/widget",
            "gh api --method=DELETE repos/acme/widget/issues/1/labels",
            "gh api -XDELETE repos/acme/widget", "gh api --method delete repos/acme/widget",
            "gh api repos/acme/widget/git/refs/heads/main -X PATCH -f sha=abc -F force=true",
            "gh api repos/acme/widget -X PATCH -f default_branch=x",
            "gh api repos/acme/widget/merges -f base=main -f head=x",
            "gh api -X PUT repos/acme/widget/contents/a.txt -f message=m -f content=eA==",
            "gh api graphql -f query='mutation { deleteIssue(input: {issueId: \"x\"}) { clientMutationId } }'",
        ])

    def test_paths_outside_the_repo_are_refused(self):
        self.refused_all([
            "cat /etc/hosts", "echo x > /tmp/x", "echo x >> ../x", "cd ..", "cd", "cd ~",
            "cd -", "ls ~/", "cat $HOME/.ssh/config", "cat ${HOME}/x", "cat ../x",
            "git -C .. status", "cp README.md \"/etc/y\"", "ls ~root",
            "curl --output=/etc/x https://example.com", "cat docs/../../x", "rm -rf \"$HOME\"",
            "sh -c 'cat /etc/hosts'", f"cat {self.tmp}/runtime/acme/widget/state.json",
        ])

    def test_a_command_the_guard_cannot_read_is_refused(self):
        self.refused_all([
            "echo 'unclosed", 'echo "unclosed', "echo $(unclosed", "echo `unclosed",
            "cat <<EOF\nno end", "cat <<EOF\n$(git status)\nEOF", "sh -c 'git status; echo \"'",
        ])
        self.assertEqual(self.hook("guard", "PreToolUse", tool_name="Bash", tool_input={})
                         ["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_git_alias_is_refused(self):
        self.git("config", "alias.pf", "push --force")
        self.refused_all([f"git pf origin {S}"])

    def test_ordinary_commands_and_pushes_to_third_shift_branches_pass(self):
        self.allowed_all([
            f"git push origin {S}", f"git push -u origin HEAD:{S}",
            f"git push origin HEAD:refs/heads/{S}", f"git -C . push origin {S}",
            f"git push --dry-run origin {S}", f"git push origin {S} 2>&1",
            f"git push -q origin {S} > push.log && git status", f"git push origin -- {S}",
            "git status", "git log origin/main..HEAD", "git diff HEAD~1", "git branch",
            "git branch -a -v", "git remote -v", "git remote get-url origin",
            "git config --get remote.origin.url", "git config remote.origin.url",
            "git config get remote.origin.url", "git config user.name t",
            "git commit -F - <<'EOF'\nIt's done: don't git push origin main; rm /etc/x\nEOF",
            'git commit -m "fix: it\'s fine"', "cat README.md", f"cat {self.target}/README.md",
            "ls > /dev/null 2>&1", "echo x >/dev/stderr", "grep -rn \"/api/v1\" .",
            "cd docs && ls", "echo a#b", "npm test # runs the suite", "gh issue view 21",
            "gh issue comment 21 --body 'will delete later'", "gh issue close 21",
            "gh issue edit 21 --add-label x", "gh api repos/acme/widget/issues",
            "gh api graphql -f query='query { viewer { login } }'",
            f"gh pr create --base main --head {S} --title t --body b",
            "uv run --script \"${CLAUDE_PLUGIN_ROOT}/cli/shift\" next --gen 1",
            f"uv run --script {ROOT}/cli/shift next --gen 1",
            'uv run --script "$CLAUDE_PLUGIN_ROOT/cli/shift" next --gen 1', "npx playwright test",
            "echo x > e2e/a.spec.ts", "mkdir -p verify/evidence && echo x > verify/evidence/a.txt",
            "uv run python -m unittest", "for f in *.py; do wc -l \"$f\"; done",
        ], env={**self.env, "CLAUDE_PLUGIN_ROOT": str(ROOT)})

    def test_a_quoted_path_directly_under_the_root_is_refused(self):
        self.refused_all(['rm -rf "/"', 'rm -rf "/usr"', "ln -s '/Users' u"])

    def test_the_plugin_root_is_outside_the_repo_but_for_the_shift_script(self):
        self.env = {**self.env, "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        self.refused_all([
            'echo x > "${CLAUDE_PLUGIN_ROOT}/cli/shift"', "cp x $CLAUDE_PLUGIN_ROOT/hooks/hooks.json",
            'cd "$CLAUDE_PLUGIN_ROOT" && rm -rf hooks', "cat $CLAUDE_PLUGIN_ROOT/cli/shift",
        ])
        expanded = self.guard(f"cp x {ROOT}/hooks/hooks.json")["hookSpecificOutput"]
        self.assertEqual(expanded["permissionDecision"], "deny")

    def test_a_branch_deleted_by_gh_is_refused(self):
        self.refused_all(["gh pr close 3 --delete-branch", "gh pr merge 3 -d"])

    def test_an_unreadable_state_fails_closed(self):
        self.assertEqual(self.guard("git status"), {})  # s1 holds the lease
        state = self.home / "acme" / "widget" / "state.json"
        state.write_text(state.read_text()[:20])  # a half-written claim
        d = self.guard("git push origin main")["hookSpecificOutput"]
        self.assertEqual(d["permissionDecision"], "deny")
        sub = self.target / "sub"
        sub.mkdir()
        d = self.guard("ls", session="s2", cwd=str(sub))["hookSpecificOutput"]
        self.assertEqual(d["permissionDecision"], "deny")  # inside its repo, whoever asks

    def test_an_unreadable_state_refuses_only_its_own_repo(self):
        state = self.home / "acme" / "widget" / "state.json"
        state.write_text(state.read_text()[:20])
        other, gh = self.tmp / "other", self.tmp / "other-gh"
        gh.mkdir()
        (gh / "fixture.json").write_text(json.dumps({"repo": "acme/other"}) + "\n")
        self.git("init", "-q", str(other), cwd=self.tmp)
        env = {**self.env, "FAKE_GH_DIR": str(gh)}  # gh names the second repo acme/other
        self.assertEqual(self.guard("ls", session="s2", cwd=str(other), env=env), {})
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertEqual(self.guard("ls", session="s2", cwd=str(plain)), {})



class Recording(Hooks):
    """An armed shift, #21 In progress, on the shift branch."""
    fixture = "admitted"

    def test_a_refusal_is_committed_to_the_ledger_and_pushed(self):
        self.refused_all(["git push origin main"])
        r = self.ledger()["refused"][0]
        self.assertEqual((r["by"], r["tool"], r["ticket"]), ("guard", "Bash", 21))
        self.assertIn("main", r["why"])
        self.assert_ledger_commit("ledger: refused")

    def test_off_the_shift_branch_a_refusal_goes_to_runtime_state(self):
        self.git("checkout", "-q", "-b", "elsewhere")
        d = self.guard("git push origin main")["hookSpecificOutput"]
        self.assertEqual(d["permissionDecision"], "deny")
        rows = (self.home / "acme" / "widget" / "refusals.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(rows[-1])["input"], "git push origin main")
        self.assertEqual(self.git("log", "-1", "--format=%s", "elsewhere"),
                         self.git("log", "-1", "--format=%s", S))  # nothing committed

    def test_a_refusal_is_logged_without_secrets_and_truncated(self):
        secrets = ["ghp_" + "a" * 30, "sk-ant-" + "b" * 20, "AKIA" + "C" * 16, "hunter2pass",
                   "tok123secret", "pw999", "sk-proj-" + "d" * 20, "sk-" + "e" * 20, "glued777",
                   "spaced888"]
        cmd = (f"GH_TOKEN={secrets[0]} git push https://x:{secrets[1]}@example.com/r main; "
               f"echo {secrets[2]}; curl password={secrets[3]} --token {secrets[4]} -p {secrets[5]}"
               f"; echo {secrets[6]} {secrets[7]}; mysql -p{secrets[8]}; echo PassWord: {secrets[9]}"
               "; echo " + "y" * 5000)
        self.assertEqual(self.guard(cmd)["hookSpecificOutput"]["permissionDecision"], "deny")
        r = self.ledger()["refused"][0]
        committed = self.git("show", f"HEAD:{LEDGER}")
        for s in secrets:
            self.assertNotIn(s, json.dumps(r))
            self.assertNotIn(s, committed)
        self.assertLess(len(r["input"]), 1000)

    # PermissionRequest and PermissionDenied

    def test_the_permission_request_hook_denies_every_prompt_but_ask_user_question(self):
        d = self.prompt()["hookSpecificOutput"]
        self.assertEqual((d["hookEventName"], d["decision"]["behavior"]),
                         ("PermissionRequest", "deny"))
        self.assertTrue(d["decision"]["message"].strip())
        self.assertEqual(self.prompt("Write")["hookSpecificOutput"]["decision"]["behavior"], "deny")
        self.assertEqual(self.prompt("AskUserQuestion"), {})
        self.assertEqual([(r["by"], r["tool"]) for r in self.ledger()["refused"]],
                         [("prompt", "Bash"), ("prompt", "Write")])

    def test_the_permission_denied_hook_logs_the_refusal_and_lets_it_stand(self):
        out = self.hook("refused", "PermissionDenied", tool_name="Bash", tool_use_id="t1",
                        tool_input={"command": "rm -rf build"}, reason="[Irreversible]")
        self.assertEqual(out, {})
        r = self.ledger()["refused"][0]
        self.assertEqual((r["by"], r["input"], r["why"]), ("auto", "rm -rf build", "[Irreversible]"))
        self.assert_ledger_commit("ledger: refused")

    # no-ops

    def test_every_hook_does_nothing_without_the_lease_or_an_armed_shift(self):
        self.assertEqual(self.guard("git push origin main", session="x", cwd=str(self.tmp)), {})
        self.assertEqual(self.guard("git status"), {})  # s1 claims the lease
        before = self.snapshot()
        self.assertEqual(self.guard("git push origin main", session="s2"), {})
        self.assertEqual(self.prompt(session="s2"), {})
        self.assertEqual(self.hook("refused", "PermissionDenied", session="s2", tool_name="Bash",
                                   tool_input={"command": "x"}, reason="r"), {})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.shift("end", "--gen", "1", "--reason", "x")[0], 0)
        before = self.snapshot()
        self.assertEqual(self.guard("git push origin main"), {})
        self.assertEqual(self.prompt(), {})
        self.assertEqual(self.hook("refused", "PermissionDenied", tool_name="Bash",
                                   tool_input={"command": "x"}, reason="r"), {})
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.home / "acme" / "widget" / "refusals.jsonl").exists())

    def test_the_plugin_wires_each_hook_to_its_entry_point(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
        wired = {(event, h.get("matcher")): h["hooks"][0]["command"].split()[-1]
                 for event, hs in hooks.items() for h in hs}
        self.assertEqual(wired[("PreToolUse", "Bash")], "guard")
        self.assertEqual(wired[("PermissionRequest", "*")], "deny-prompt")
        self.assertEqual(wired[("PermissionDenied", "*")], "refused")
        command = next(h["hooks"][0]["command"] for h in hooks["PreToolUse"]
                       if h["matcher"] == "Bash")
        p = subprocess.run(["sh", "-c", command], cwd=self.target, capture_output=True, text=True,
                           env={**self.env, "CLAUDE_PLUGIN_ROOT": str(ROOT)},
                           input=json.dumps({"session_id": "s1", "cwd": str(self.target),
                                             "tool_name": "Bash",
                                             "tool_input": {"command": "git push origin main"}}))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


class RefusalsAreNotProgress(Stopping, Hooks):
    fixture = "admitted"

    def test_a_refusal_between_blocked_stops_does_not_reset_the_count(self):
        self.beat(0)
        self.blocked()
        self.blocked()
        self.guard("git push origin main")
        self.blocked()
        self.assertEqual(self.state(21)["state"], "Stalled")


if __name__ == "__main__":
    unittest.main()
