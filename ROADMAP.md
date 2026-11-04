# Roadmap

What SpamGuard intends to do over the coming year, and what it deliberately won't do. Plans change with what
users report, so this is a direction rather than a promise. Suggestions are welcome as issues.

## Next

1. **Keep pace with openHop.** Support each new openHop release, and move to openHop's own interfaces as they
   appear (for example richer rule fields), so fewer workarounds are needed.
2. **Easier to find and install.** A listing in openHop's plugin catalogue, so SpamGuard can be installed
   without downloading a file by hand.
3. **Measure accuracy.** Use the labels and the replay tool to check how often SpamGuard gets it right on
   real installs, and tune from those numbers rather than guesses. Every detection change is replayed on real,
   labelled traffic before it ships.
4. **Settings advisor, next steps.** Today it only suggests. Next: try a suggested change in record-only mode
   first, undo it at once if genuine messages start being held, and later make small, low-risk changes by
   itself if you switch that on.
5. **Experiments that prove themselves** move out of the Experimental section; ones that don't are removed.
6. **Clearer on a phone.** Keep reducing the wording and putting the useful numbers first.
7. **Include suggested surge blocks in the level preview,** so you can see what each protection level would have
   suggested on your own traffic. Today the preview covers messages only.

## Later

1. **More languages** for the web page.
2. **Simpler sharing of settings** between repeater operators in the same area.
3. **Better flood reports** that help operators talk to the owner of the repeater a flood comes in through.

## What SpamGuard won't do

1. **Judge what people say.** It won't filter opinions, words or topics, and it has no "block this person"
   button. Hiding a person is each user's choice in their own app.
2. **Touch direct messages or acknowledgements.** Only channel spam and floods are its business. A flood of
   requests or group data can be held from the repeater it comes through, using counts only; direct messages
   and acknowledgements never are.
3. **Report back.** No telemetry, no usage statistics, no calls home. The only outside contact is the
   optional update check and map directory.
4. **Need the cloud or an account.** It runs entirely on the repeater.
5. **Publish how its detection works in detail.** That would only help spammers get round it.
6. **Rely on downloaded block lists.** It learns from your own mesh, so it keeps working offline and a list
   can't be gamed or go stale.
