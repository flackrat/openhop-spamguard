# Roadmap

What SpamGuard intends to do over the coming year, and what it deliberately won't do. Plans change with what
users report, so this is a direction rather than a promise. Suggestions are welcome as issues.

The aim is to be the careful, explainable protection layer for a MeshCore repeater. It doesn't try to win on
the number of rules. It aims to stop what harms the shared channel while making it as hard as possible to hold
back someone who has done nothing wrong. [Our principles](docs/principles.md) say how.

## Next

1. **Fairer flood limits.** FloodGuard measures airtime, not message counts. Next it should give each kind of
   traffic (messages, adverts, control) its own share, and allow short bursts within a steady limit. It should
   step up and back down smoothly, so a busy evening doesn't flip it on and off. A busy channel is not evidence
   that anyone is misbehaving.
2. **Preview before you apply.** The protection level already shows what each level would have held on your
   own traffic. The same should work for blocks and rules: what a change would hold and who it would affect,
   with a record-only trial first. It will use the same checks as live blocking, so the preview can't disagree
   with what really happens.
3. **Every decision explained and reversible.** For any held message: what happened, what it was based on,
   what was done, what else that affects, and how to undo it, all on one screen per incident.
4. **New names handled gently.** A first ordinary message from someone new shouldn't need your attention, but
   it never skips the checks that catch campaigns and repeats. This will be replayed on real, labelled traffic
   before it ships.
5. **Keep pace with openHop.** Support each new openHop release, and use its own interfaces as they appear:
   richer rule fields, and route traces for the optional route checks, which wait for them.
6. **Detection separate from openHop.** Split the detection code from the openHop-specific parts, so it can be
   tested on its own and could later work with other MeshCore repeaters.
7. **Published, repeatable measurements.** How often genuine messages are held, how much spam is caught, CPU,
   memory and SD card use, and airtime saved, from tests anyone can rerun.
8. **Easier to find and install.** A listing in openHop's plugin catalogue.

## Later

1. **Several radios.** Separate airtime, congestion and limits for each radio on one repeater. The design is
   ready; it waits for someone with more than one radio to test it.
2. **More languages** for the web page.
3. **Simpler sharing of settings** between repeater operators in the same area. Export and import of your own
   decisions exists; live sync may follow if operators want it.
4. **Better flood reports** that help operators talk to the owner of the repeater a flood comes in through.

## What SpamGuard won't do

1. **Judge what people say.** It won't filter opinions, words or topics, and it has no "block this person"
   button. Hiding a person is each user's choice in their own app.
2. **Treat a clue as proof.** A shared repeater, a similar time or a guessed place on the map is evidence to
   look at, never a reason by itself to hold someone. A busy route is shared by many innocent people.
3. **Get harsher on its own.** Better detection should mean better evidence and smaller, shorter holds, not
   more of them. Automatic holds expire, and anything it suggests you can preview and undo.
4. **Touch direct messages or acknowledgements.** Only channel spam and floods are its business.
5. **Report back.** No telemetry, no usage statistics, no calls home. The only outside contact is the
   optional update check and map directory.
6. **Need the cloud or an account.** It runs entirely on the repeater.
7. **Interfere with the radio.** Any transmitting feature is optional, off by default, rare and at quiet
   times. It never jams, floods or pretends to be someone else.
8. **Publish how its detection works in detail.** That would only help spammers get round it.
9. **Rely on downloaded block lists.** It learns from your own mesh, so it keeps working offline and a list
   can't be gamed or go stale.
