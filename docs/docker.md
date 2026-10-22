# Running SpamGuard in Docker

**Most people should use the openHop plugin instead** ([openhop-plugin.md](openhop-plugin.md)): it runs inside openHop's own container, so there's no second container to look after. This guide is for anyone who prefers SpamGuard in a container of its own. If you already run it this way, SpamGuard's page offers **Move to the plugin**.

If your openHop runs in Docker (or as an Unraid app), you can run SpamGuard as a container next to it. The container talks to openHop only through openHop's web API, the same as the normal install, so it needs no access to openHop's files.

## What you need

- openHop running in Docker, with its web API reachable from other containers (it listens on port 8000 by default).
- An openHop API token: openHop dashboard > System > API Tokens.
- Docker with the compose plugin. Images are published for 64-bit and 32-bit Raspberry Pi OS and for ordinary PCs.

## Set it up

1. Download the example compose file into a folder of its own (or next to your openHop compose file):

   ```
   mkdir spamguard && cd spamguard
   curl -fsSLo docker-compose.yml https://raw.githubusercontent.com/flackrat/openhop-spamguard/main/docker-compose.example.yml
   ```

2. Edit `docker-compose.yml`: paste your token into `OPENHOP_API_KEY`, and set `OPENHOP_URL` to openHop's address as seen from the SpamGuard container (see "Reaching openHop" below). Set `TZ` to your time zone so the charts use local time.

3. Start it:

   ```
   docker compose up -d
   ```

4. Open `http://<your-host>:8091/`. Leave it in **Monitor** for a day (it shows what it *would* stop), then switch to **Protect**. If you don't come back, it switches itself to Protect once it has watched for a day and seen enough spam (the Overview shows when, with a **Stay in Monitor** button).

Everything SpamGuard learns (blocks, known people, settings and the evidence log, if you switch it on) is kept in the `spamguard-data` folder next to the compose file, so it survives restarts and updates.

## Reaching openHop

- **Same compose file or same Docker network:** use openHop's service name. openHop's own compose file calls it `openhop-repeater`, so the address is `http://openhop-repeater:8000`. Some examples call it `repeater` instead; `docker compose ps` in your openHop folder shows the name.
- **Different compose files:** each compose file gets its own network, so either join SpamGuard to openHop's network (it is usually called `<openhop folder>_default`; add it under `networks:` as an external network), or use the host's address, for example `http://192.168.1.20:8000`.
- **openHop uses host networking:** give SpamGuard `network_mode: host` too, set `OPENHOP_URL` to `http://127.0.0.1:8000`, and remove the `ports:` section.

The Health page shows straight away whether SpamGuard can reach openHop and whether the token works.

## Settings

Most settings are changed on SpamGuard's own page, and those choices are kept in the data folder. A few can also be given as environment variables in the compose file:

| Variable | What it does |
|---|---|
| `OPENHOP_API_KEY` | Your openHop API token (required) |
| `OPENHOP_URL` | Where openHop's web API is (default `http://127.0.0.1:8000`) |
| `SPAMGUARD_MODE` | `monitor` or `protect` at first start |
| `SPAMGUARD_SENSITIVITY` | `relaxed`, `balanced` or `strict` at first start |
| `SPAMGUARD_CHANNELS` | Extra hashtag channels to protect, comma-separated, e.g. `#chat,#test` |
| `SPAMGUARD_PASSWORD` | Ask for a password before anything is changed on the page |
| `TZ` | Your time zone, e.g. `Europe/Amsterdam` |

You can also put a `config.yaml` (the same file the normal install uses) in the data folder; settings in it take priority over the environment, apart from the token.

## Updating

SpamGuard's page tells you when a new version is out. In Docker it can't update itself, so in the folder with your compose file run:

```
docker compose pull && docker compose up -d
```

## Differences from the normal install

- **No Update button**: update by pulling the new image, as above.
- **No automatic openHop fixes.** On a normal install SpamGuard can apply openHop's rule-check fix by editing one file inside openHop. One container can't sensibly edit another's files, and an openHop image update would undo it anyway, so the Docker version leaves openHop alone. The rule-check fix is for an openHop bug ([#520](https://github.com/openhop-dev/openhop_repeater/issues/520)) that goes away once openHop releases its own fix.
- **Restarts** are handled by Docker (`restart: unless-stopped`), and the image has a health check on SpamGuard's `/health` page, so `docker ps` shows whether it is healthy.

## Removing it

Stop SpamGuard, then take its rules back out of openHop (your own rules are left alone):

```
docker compose down
docker compose run --rm spamguard python3 spamguard.py --remove-rules
```

Delete the `spamguard-data` folder too if you no longer want its history.
