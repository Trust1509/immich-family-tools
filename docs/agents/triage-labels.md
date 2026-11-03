# Triage Labels

The skills speak in terms of five canonical triage roles. (Woher diese Skills kommen und wie sie eingerichtet werden: `skills.md` — sie liegen pro Rechner, nicht im Repo.) This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.
(In einem frischen Repo existieren die Labels noch nicht auf GitHub — sie werden in Setup-Schritt 2 angelegt (`setup-checkliste.md`, „Issue-Tracker", per `gh label create`); `gh issue edit --add-label` erwartet sie danach.)
