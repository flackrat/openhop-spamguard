# How spam works, and the words used here

MeshCore radios pass messages on for each other: a message sent on a **channel** (such as Public) is repeated by every **repeater** that hears it, hop by hop, until it has spread across the mesh. That is what makes the mesh work, and also what makes spam so annoying: one spammer's message, sent once, is carried by every repeater to everyone. Spammers make it worse by using a new made-up name for each message, sending the same text under many names, or flooding the radio with packets until nobody else can get a word in. A repeater can't stop someone sending, but it can refuse to pass something on. That's what SpamGuard does, so the spam stops at your repeater instead of travelling on.

| Word | What it means here |
|---|---|
| **Repeater** | A radio that passes messages on for others. SpamGuard runs on yours. |
| **openHop** | The software that runs a MeshCore repeater on a Raspberry Pi or similar. SpamGuard is a plugin for it. |
| **Channel** | A shared group chat. Public is open to all; hashtag channels such as #chat need only their name; private channels need a key. |
| **Hop** | One radio passing a message to the next. A message that has come 10 hops has been repeated by 10 repeaters. |
| **Route (path)** | The list of repeaters a message came through, shown as short codes such as `27>B1>7E`, read from where it entered the mesh. |
| **Route code (path hash)** | The short code a repeater is known by in a route: the first 2, 4 or 6 characters of its ID. Short codes are shared by many repeaters, which is why working out where spam came from takes some care. |
| **Advert** | A message a repeater sends now and then to say it exists, often with its location. SpamGuard uses adverts to learn which code is which repeater. |
| **Airtime** | How much of the time the radio channel is busy. LoRa radios are slow, so airtime is precious; a flood can use it all up. |
| **Flood packet** | A packet repeated by everyone (most channel messages and adverts). A **direct** message follows a set route instead and isn't touched. |
| **Unscoped** | A flood packet sent without a region. `flood.max.unscoped` is MeshCore's limit on how many hops those may travel; FloodGuard keeps the same kind of limit. |
| **Made-up name / rotating identity** | A spammer using a new random name (such as UD6DWREK) for each message, or a repeater that keeps changing its ID, so it can't simply be blocked by name. |
| **Known people** | Names SpamGuard has seen sending genuine messages. They are let through blocks meant for spam. |
| **Rules (policy)** | openHop's list of what to pass on and what to drop, kept in its `policy.yaml`. SpamGuard adds its own rules there and never changes yours. |
| **Monitor / Protect** | Monitor only shows what SpamGuard would stop; Protect actually stops it. |
| **Protection level** | One slider from Gentle to Tough: how firmly SpamGuard pushes back. |
| **Evidence log** | An optional daily record, kept only on your repeater, of the channel messages SpamGuard read and what it did. It lets you look back over a week and check its decisions. |

**Version numbers.** The release number is SpamGuard's (6.19.0, for example). FloodGuard, the flood protection inside SpamGuard since 6.0, has its own number (such as 1.3.1) that only goes up when FloodGuard itself changes; both come in the same download. openHop is a separate project with its own numbers; SpamGuard needs openHop 1.1.2 or later. The top of the [changelog](../CHANGELOG.md) sums up what changed between the big versions.
