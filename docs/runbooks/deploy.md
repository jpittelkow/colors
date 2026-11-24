# Deploy and run

The server is one container, `kidtube`. These steps use an Unraid host as the example; any Docker host works.

| What | Example |
|---|---|
| Parents' page | `http://<host>:8460/admin/` |
| Unraid template | `/boot/config/plugins/dockerMan/templates-user/my-kidtube.xml` (start from `unraid/my-kidtube.xml`) |
| App data (database, cookies file, your own characters) | `/mnt/user/appdata/kidtube` → `/data` |
| Videos | `/mnt/user/Media/Kids` → `/library` |
| Runs as | `--user 99:100` (nobody:users on Unraid) |
| Image | `kidtube:latest`, built on the host from the repo |

Without Unraid:

```bash
docker build -t kidtube .
docker run -d --name kidtube -p 8460:8460 -v /path/to/data:/data -v /path/to/videos:/library   -e KIDTUBE_ADMIN_PASSWORD=change-me kidtube
```

## Update after a change

```bash
bash scripts/deploy.sh
```

It needs `KIDTUBE_HOST=user@host` (in the environment, or in `deploy.local.env` in the repo root, which git ignores).
It refuses to run with uncommitted changes, builds the image on the host from `git archive HEAD`, tags it
`kidtube:latest` and `kidtube:<commit>`, and recreates the container from the template with Unraid's
`update_container`.

## The PO token helper

YouTube flags a server that downloads a lot ("Sign in to confirm you're not a bot"). A PO token helper avoids most of
that. Run it next to colors and point `KIDTUBE_POT_URL` at it:

```bash
docker run -d --name bgutil-pot-provider --init --restart unless-stopped -p 4416:4416   brainicism/bgutil-ytdlp-pot-provider:2.0.2
```

Keep its tag equal to the `bgutil-ytdlp-pot-provider` version in `server/requirements.txt` (the yt-dlp plugin that
talks to it). Check it with `curl http://<host>:4416/ping`. When YouTube blocks anyway, downloads take a break by
themselves (ADR 0004) and the activity pill says until when.

## Your own characters

Profile characters beyond the built-in set go in `/data/characters/<id>.svg` (ADR 0036). They show up in the picker
next to the built-in ones. Keep artwork you don't own out of the repository; this folder is the place for it.

## Roll back

```bash
ssh <host> 'docker images kidtube'                 # find the previous commit tag
ssh <host> 'docker tag kidtube:<commit> kidtube:latest && /usr/local/emhttp/plugins/dynamix.docker.manager/scripts/update_container kidtube'
```

Database migrations take a backup first: `<data>/kidtube.pre-migrate-*.db` (last five kept).
To restore one: stop the container, copy it over `kidtube.db` (and delete `kidtube.db-wal`, `kidtube.db-shm`), start.

## First run

`KIDTUBE_ADMIN_PASSWORD` in the template sets the parents' password once, if none is set yet. After that it is
ignored; change the password in the page (More, Change password), which also signs out other sessions.

## yt-dlp needs a JavaScript runtime

YouTube now needs a JavaScript runtime to solve its player challenges. The image ships deno. yt-dlp rejects old
deno versions as "unsupported" and then every video comes back "This video is not available": check with

```bash
ssh <host> 'docker exec kidtube python -m yt_dlp -v --simulate "https://www.youtube.com/watch?v=<id>" 2>&1 | grep -i "JS runtimes"'
```

When downloads start failing the same way, bump deno (Dockerfile) or yt-dlp (`server/requirements.txt`) and deploy.

## Not done yet

- A health check: `http://<host>:8460/healthz` answers 200 when the server is up (good for Uptime Kuma).
- Alerts to Telegram (ADR 0023) are not built.
