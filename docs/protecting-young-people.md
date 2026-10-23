# Protecting young people on MeshCore

SpamGuard doesn't have an under-18 mode, and this page explains why, then shows what works instead.

## Why SpamGuard doesn't do this

A MeshCore message carries a display name and nothing else, so a repeater can't tell how old anyone is. A switch labelled "under 18 protection" would really be a language filter, and a language filter can't see the thing that matters most. Grooming is usually polite and quiet, and it moves to private messages. A parent who sees a protection switch turned on might relax, and that false comfort is a bigger risk than having no switch.

SpamGuard also promises that it judges how messages are sent, never what people say. That promise is why people can trust it on a repeater that carries everyone's traffic. What counts as unsuitable language differs between communities and countries, and anything a repeater drops disappears for everyone downstream without them knowing why.

## What works better

**1. Use a private channel with its own key.** The Public channel and hashtag channels can be read and joined by anyone, adults included. For a youth group, school club or event, create a channel with its own secret key and give the key only to the people who should have it. Adults who run the group should be on it, and a young person's first contact with strangers should never be through an open channel.

**2. Supervise.** Devices belong in the hands of young people who have been told what the mesh is, who can read their messages, and what to do if someone makes them uncomfortable. Direct messages are the place to be most careful, and no repeater can see inside them.

**3. Use the filters in your own app.** MeshCore apps and sites let each person hide or block a sender, a repeater or a channel for themselves. That is the right place for personal choices, because it changes only what that person sees.

**4. Report and talk to the community.** If someone is behaving badly towards a young person, take screenshots, report it to the people running the local community channel, and, if a young person may be at risk, to the police or the relevant child protection service in your country. Don't deal with it alone.

## If you run a repeater for a youth channel

SpamGuard doesn't write language rules, but it leaves your own openHop rules alone, so you can add them yourself in openHop's policy settings for the channel you run. A rule names the channel by its key, checks for a piece of text, and drops the message. Here is the shape, with a placeholder word:

```yaml
- id: 100
  name: youth channel word filter
  enabled: true
  if:
    all:
      - field: payload_type
        op: equals
        value: 5
      - field: channel_hash
        op: equals
        value: "<your channel key>"
      - field: channel_message_body
        op: contains
        value: "example-word"
  then:
    action: drop
```

A few things to know before you do this:

1. Only use it on a channel you run for a defined group, never on Public or a shared hashtag channel.
2. The channel key is a secret, and it will sit in your policy file, so keep that file private.
3. Check whether your openHop version matches text with or without regard to capital letters, and add variants if it doesn't.
4. A word list is blunt. It will miss clever spelling and will catch innocent words that contain a banned one, so test it on the channel before relying on it, and tell the group it is there.
5. It is your rule and your responsibility. SpamGuard doesn't read, apply or take any part in it.

This page is general information about how the tools behave. It is not legal or safeguarding advice, and the right steps depend on your country and your organisation's own safeguarding policy.
