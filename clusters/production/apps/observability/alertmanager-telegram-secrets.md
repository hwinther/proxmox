# Alertmanager Telegram delivery — `alertmanager-telegram` Secret

Alertmanager (in `kube-prometheus-stack-helmrelease.yaml`) sends alerts to Telegram via the native
`telegram_configs` receiver. The bot token is a credential, so it lives in a Secret that is mounted
into the Alertmanager pods (`alertmanagerSpec.secrets: [alertmanager-telegram]` →
`/etc/alertmanager/secrets/alertmanager-telegram/bot-token`, referenced as `bot_token_file`). The
token is **never** committed.

## 1. Create the bot + get the token

1. In Telegram, message **@BotFather** → `/newbot`, follow the prompts.
2. BotFather returns a token like `123456789:AAExampleExampleExampleExampleExample`. That's the
   `bot-token` value below.

## 2. Get your chat ID

1. Send any message to your new bot (so it's allowed to message you), then:
   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq '.result[].message.chat.id'
   ```
2. Use that integer as `chat_id` in `kube-prometheus-stack-helmrelease.yaml`
   (replace the `000000000` placeholder). It is not a secret, so it stays in Git.
   - For a **group**, add the bot to the group, post a message there, and use the negative
     group chat ID from the same `getUpdates` call.

## 3. Create the Secret

```bash
kubectl create secret generic alertmanager-telegram \
  -n observability-production \
  --from-literal=bot-token='123456789:AAExampleExampleExampleExampleExample'
```

The key **must** be `bot-token` (the mount path / `bot_token_file` depends on it).

## 4. Apply + verify

After the Secret exists and `chat_id` is set, commit/push so Flux reconciles. Then:

```bash
# Confirm Alertmanager loaded the config without error:
kubectl -n observability-production logs sts/alertmanager-obs-kps-kube-prometheus-st-alertmanager -c alertmanager | grep -i telegram

# Send a test alert straight to Alertmanager:
kubectl -n observability-production exec sts/alertmanager-obs-kps-kube-prometheus-st-alertmanager -c alertmanager -- \
  amtool alert add TestAlert severity=warning --annotation=summary="test from amtool" \
  --alertmanager.url=http://localhost:9093
```

A message should arrive in Telegram within a few seconds.

## Rotating the token

`kubectl create secret generic alertmanager-telegram ... --dry-run=client -o yaml | kubectl apply -f -`
(generated locally, never committed), then restart Alertmanager if it doesn't pick it up:
`kubectl -n observability-production rollout restart sts/alertmanager-obs-kps-kube-prometheus-st-alertmanager`.
