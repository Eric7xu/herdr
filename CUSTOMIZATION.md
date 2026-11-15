# Custom HERDR build

This branch keeps the HERDR 0.9.5 runtime and protocol unchanged.
The patch changes the embedded Agent Skill.
It permits external read-only access when the user names the target and grants access.
It does not change authentication, socket permissions, macOS permissions, or server access controls.
Other machines can keep the official HERDR release.

## Source and versions

The upstream base is tag `v0.9.5`, commit `2ecf19a92fc3a7fff75b6ce3655ef04f4625ec01`.
The `master` branch follows upstream.
The `custom` branch keeps the reviewed patch.
Custom release tags and Homebrew revisions identify patch releases.
The runtime version stays `0.9.5` because upstream remote installation uses the official version catalog.
Do not change protocol constants to conceal an incompatible change.

## Tests and builds

The existing CI workflow runs the upstream tests.
On Unix runners, `tests/custom_standard_compat.rs` also runs the mixed-release test.
The test downloads the official 0.9.5 binary and compares its SHA-256 with a pinned value.
It starts separate temporary servers and uses explicit socket paths.
It tests the custom client with the official server and the reverse combination.
It reads workspaces, tabs, panes, and agents in those temporary sessions.

The test does not connect to a user's Mac or VPS.
It does not test all historical releases, SSH forwarding, terminal UI attachment, or Windows compatibility.
Use the actual deployment matrix before expanding the supported version range.
The manual artifact workflow builds the macOS binaries in GitHub Actions.
A release must use a commit that passed CI and completed the artifact build.

## Installation and updates

The separate `Eric7xu/homebrew-tools` repository supplies `herdr-custom` after a release passes its tests.
The formula installs prebuilt binaries with fixed SHA-256 values.
It does not compile HERDR on the user's Mac.
The package remains unlinked until the user chooses to switch.
Do not replace or restart an active HERDR server during installation.

If a new upstream version is needed, select its stable tag first.
Apply the small patch to that base.
Update the official reference binaries and their pinned hashes.
Run the upstream and mixed-release tests before publishing.
Use the custom Homebrew tap to update custom installations.
Keep official installations on their normal update path.

## Scope of the Skill patch

External readers must select an existing local session or a saved SSH machine.
They must use target IDs from that endpoint, not the UI focus or a different machine.
The external exception does not permit commands, keystrokes, prompts, layout changes, or configuration changes.
The Skill is guidance for the Agent, not a security sandbox.
