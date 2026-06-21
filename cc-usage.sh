#!/usr/bin/env bash
# cc-usage - Estimate Claude Code spend from local transcripts.
#
# Walks ~/.claude/projects/*/*.jsonl, sums token usage from assistant
# messages within a date range, applies per-model pricing, and prints
# an estimated USD breakdown.
#
# Costs are estimates: web_fetch is treated as free (no published per-request
# rate) and any negotiated/tier discounts aren't applied. Opus 4.6+/Sonnet 4.6
# bill the full 1M context at the standard rate, so no >200k surcharge applies.

set -euo pipefail

PROJECTS_DIR="${CC_PROJECTS_DIR:-$HOME/.claude/projects}"

# Pricing: USD per million tokens. Columns:
#   model | input | output | cache_read | cache_creation_5m | cache_creation_1h
# Cache multipliers follow Anthropic's published ratios (read 0.1x, 5m 1.25x,
# 1h 2x of input). Unknown models fall through to "(unknown)" with $0 rates.
# Cache creation is read from the nested cache_creation.ephemeral_{5m,1h} breakdown;
# transcripts that carry only the flat cache_creation_input_tokens field (older
# sessions) fall back to billing that total at the 5m rate (see emit_rows).
PRICING=$(cat <<'EOF'
claude-fable-5  10  50  1.00    12.50   20
claude-opus-4-8 5   25  0.50    6.25    10
claude-opus-4-7 5   25  0.50    6.25    10
claude-opus-4-6 5   25  0.50    6.25    10
claude-sonnet-4-6   3   15  0.30    3.75    6
claude-sonnet-4-5-20250929  3   15  0.30    3.75    6
claude-haiku-4-5-20251001   1   5   0.10    1.25    2
EOF
)

# $10 per 1000 web_search requests.
WEB_SEARCH_USD_PER_REQ="0.01"

usage() {
    cat <<EOF
Usage: cc-usage [options]

    --since DATE     Start of range (YYYY-MM-DD or ISO-8601). Default: 14 days ago.
    --until DATE     End of range (YYYY-MM-DD or ISO-8601). Default: now.
    --days N         Shortcut for --since=N days ago (overrides --since).
    --by FIELD       Group by: model (default) | project | day | session
    --exclude RE     Drop rows whose decoded project path matches RE (extended regex).
    --include RE     Keep only rows whose decoded project path matches RE.
    --json           Emit JSON rows instead of a table.
    --projects DIR   Override transcript root (default: ~/.claude/projects).
    -h, --help       Show this help.

Examples:
    cc-usage                       # last 14 days, by model
    cc-usage --days 30 --by day    # last 30 days, daily breakdown
    cc-usage --by project          # spend per repo
    cc-usage --since 2026-05-01 --until 2026-05-15 --by day
EOF
}

since=""
until_=""
days=14
group_by="model"
json=0
exclude_re=""
include_re=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --since)    since="$2"; days=""; shift 2 ;;
        --until)    until_="$2"; shift 2 ;;
        --days)     days="$2"; since=""; shift 2 ;;
        --by)       group_by="$2"; shift 2 ;;
        --exclude)  exclude_re="$2"; shift 2 ;;
        --include)  include_re="$2"; shift 2 ;;
        --json)     json=1; shift ;;
        --projects) PROJECTS_DIR="$2"; shift 2 ;;
        -h|--help)  usage; exit 0 ;;
        *)          echo "cc-usage: unknown arg: $1" >&2; usage >&2; exit 2 ;;
    esac
done

case "$group_by" in
    model|project|day|session) ;;
    *) echo "cc-usage: --by must be one of: model, project, day, session" >&2; exit 2 ;;
esac

[[ -d "$PROJECTS_DIR" ]] || { echo "cc-usage: no such dir: $PROJECTS_DIR" >&2; exit 1; }

if [[ -n "$days" ]]; then
    since=$(date -u -d "$days days ago" +%Y-%m-%dT00:00:00Z)
fi
case "$since"  in *T*) ;; "") since=$(date -u -d "14 days ago" +%Y-%m-%dT00:00:00Z) ;; *) since="${since}T00:00:00Z" ;; esac
case "$until_" in *T*) ;; "") until_=$(date -u +%Y-%m-%dT23:59:59Z) ;; *) until_="${until_}T23:59:59Z" ;; esac

# Emit TSV rows: day \t project \t session \t model \t in \t out \t cread \t c5m \t c1h \t websrch
emit_rows() {
    find "$PROJECTS_DIR" -name '*.jsonl' -print0 2>/dev/null \
    | xargs -0 -I{} sh -c '
        f="$1"
        # decode project from the directory name: leading "-" then "/" -> "-"
        dir=$(basename "$(dirname "$f")")
        proj=$(printf "%s" "$dir" | sed -e "s#^-#/#" -e "s#-#/#g")
        session=$(basename "$f" .jsonl)
        jq -r --arg since "$2" --arg until "$3" --arg proj "$proj" --arg session "$session" '"'"'
            select(.type == "assistant" and .message.usage and .timestamp)
            | select(.timestamp >= $since and .timestamp <= $until)
            | [
                (.timestamp | split("T")[0]),
                $proj,
                $session,
                (.message.model // "(unknown)"),
                (.message.usage.input_tokens // 0),
                (.message.usage.output_tokens // 0),
                (.message.usage.cache_read_input_tokens // 0),
                (.message.usage.cache_creation.ephemeral_5m_input_tokens // .message.usage.cache_creation_input_tokens // 0),
                (.message.usage.cache_creation.ephemeral_1h_input_tokens // 0),
                (.message.usage.server_tool_use.web_search_requests // 0),
                (.uuid // "")
                ] | @tsv
        '"'"' "$f"
    ' _ {} "$since" "$until_"
}

emit_rows | awk -v group_by="$group_by" -v json="$json" -v pricing="$PRICING" \
                -v websrch_rate="$WEB_SEARCH_USD_PER_REQ" -v since="$since" -v until_="$until_" \
                -v exclude_re="$exclude_re" -v include_re="$include_re" '
BEGIN {
    FS = "\t"; OFS = "\t"
    n = split(pricing, lines, "\n")
    for (i = 1; i <= n; i++) {
        if (lines[i] == "") continue
        split(lines[i], p, "\t")
        rates_in[p[1]]    = p[2] + 0
        rates_out[p[1]]   = p[3] + 0
        rates_cr[p[1]]    = p[4] + 0
        rates_c5m[p[1]]   = p[5] + 0
        rates_c1h[p[1]]   = p[6] + 0
        known[p[1]]       = 1
    }
}
{
    day = $1; proj = $2; sess = $3; model = $4
    in_tok = $5+0; out_tok = $6+0; cread = $7+0; c5m = $8+0; c1h = $9+0; web = $10+0
    uuid = $11

    if (exclude_re != "" && proj ~ exclude_re) next
    if (include_re != "" && proj !~ include_re) next

    # Dedupe by uuid: same assistant message can appear in multiple
    # transcripts when a session is resumed into a new file.
    if (uuid != "") {
        if (uuid in seen_uuid) { dup_count++; next }
        seen_uuid[uuid] = 1
    }

    if (group_by == "model")        key = model
    else if (group_by == "project") key = proj
    else if (group_by == "day")     key = day
    else                            key = sess "  [" proj "]"

    # cost: per-model rate; if unknown, model rates are zero -> $0
    rate_in  = rates_in[model]   + 0
    rate_out = rates_out[model]  + 0
    rate_cr  = rates_cr[model]   + 0
    rate_c5m = rates_c5m[model]  + 0
    rate_c1h = rates_c1h[model]  + 0

    cost  = (in_tok  * rate_in   / 1e6) \
            + (out_tok * rate_out  / 1e6) \
            + (cread   * rate_cr   / 1e6) \
            + (c5m     * rate_c5m  / 1e6) \
            + (c1h     * rate_c1h  / 1e6) \
            + (web     * websrch_rate)

    sum_cost[key] += cost
    sum_in[key]   += in_tok
    sum_out[key]  += out_tok
    sum_cr[key]   += cread
    sum_c5m[key]  += c5m
    sum_c1h[key]  += c1h
    sum_web[key]  += web
    msgs[key]++
    if (!(model in seen_models)) { seen_models[model] = 1; if (!known[model] && model != "(unknown)" && model != "<synthetic>") unknown_models[model] = 1 }

    grand_cost += cost
}
END {
    if (length(sum_cost) == 0) {
        printf("(no data in range %s .. %s)\n", since, until_) > "/dev/stderr"
        exit 0
    }

    # sort keys by descending cost
    nkeys = 0
    for (k in sum_cost) keys[++nkeys] = k
    for (i = 1; i <= nkeys; i++)
        for (j = i+1; j <= nkeys; j++)
            if (sum_cost[keys[j]] > sum_cost[keys[i]]) { t = keys[i]; keys[i] = keys[j]; keys[j] = t }

    # per-group cost distribution (keys[] is sorted by descending cost)
    cost_mean = grand_cost / nkeys
    cost_max  = sum_cost[keys[1]]
    cost_min  = sum_cost[keys[nkeys]]
    if (nkeys % 2 == 1) cost_median = sum_cost[keys[(nkeys + 1) / 2]]
    else                cost_median = (sum_cost[keys[nkeys / 2]] + sum_cost[keys[nkeys / 2 + 1]]) / 2

    if (json) {
        printf("{\n  \"since\": \"%s\",\n  \"until\": \"%s\",\n", since, until_)
        printf("  \"group_by\": \"%s\",\n", group_by)
        printf("  \"total_usd\": %.4f,\n", grand_cost)
        printf("  \"summary\": {\"count\": %d, \"mean_usd\": %.4f, \"median_usd\": %.4f, \"min_usd\": %.4f, \"max_usd\": %.4f},\n",
            nkeys, cost_mean, cost_median, cost_min, cost_max)
        printf("  \"rows\": [\n")
        for (i = 1; i <= nkeys; i++) {
            k = keys[i]
            printf("    {\"key\": \"%s\", \"cost_usd\": %.4f, \"messages\": %d, \"input\": %d, \"output\": %d, \"cache_read\": %d, \"cache_5m\": %d, \"cache_1h\": %d, \"web_search\": %d}%s\n",
                k, sum_cost[k], msgs[k], sum_in[k], sum_out[k], sum_cr[k], sum_c5m[k], sum_c1h[k], sum_web[k],
                (i < nkeys ? "," : ""))
        }
        printf("  ]\n}\n")
        exit 0
    }

    # human table
    printf("Claude Code spend  %s  ..  %s\n", since, until_)
    printf("Grouped by: %s    Estimated total: $%.2f\n\n", group_by, grand_cost)

    # column widths
    key_w = length(group_by)
    for (i = 1; i <= nkeys; i++) if (length(keys[i]) > key_w) key_w = length(keys[i])
    if (key_w > 60) key_w = 60

    fmt = "%-" key_w "s  %10s  %7s  %10s  %10s  %10s  %10s  %10s  %6s\n"
    printf(fmt, toupper(group_by), "COST", "MSGS", "INPUT", "OUTPUT", "C-READ", "C-5MIN", "C-1HR", "WEB")
    sep = ""
    total_w = key_w + 2 + 10 + 2 + 7 + 2 + 10*5 + 4*2 + 2 + 6
    for (i = 0; i < total_w; i++) sep = sep "-"
    print sep

    for (i = 1; i <= nkeys; i++) {
        k = keys[i]
        disp = k
        if (length(disp) > key_w) disp = "..." substr(disp, length(disp) - key_w + 4)
        printf(fmt, disp, sprintf("$%.2f", sum_cost[k]), msgs[k],
            hum(sum_in[k]), hum(sum_out[k]), hum(sum_cr[k]), hum(sum_c5m[k]), hum(sum_c1h[k]), sum_web[k])
    }

    print sep
    printf("Per-%s over %d %s(s):   mean $%.2f   median $%.2f   min $%.2f   max $%.2f\n",
        group_by, nkeys, group_by, cost_mean, cost_median, cost_min, cost_max)

    if (length(unknown_models) > 0) {
        printf("\nNote: no pricing for model(s):")
        for (m in unknown_models) printf(" %s", m)
        printf("  - shown at $0.\n")
    }
    printf("\n(Estimated pay-as-you-go API cost. If you are on a Max/Pro subscription,\n your actual billed cost is the subscription fee, not this number.)\n")
}
function hum(n,   s) {
    if      (n >= 1e9) { s = sprintf("%.1fB", n/1e9); sub(/\.0B$/, "B", s) }
    else if (n >= 1e6) { s = sprintf("%.1fM", n/1e6); sub(/\.0M$/, "M", s) }
    else if (n >= 1e3) { s = sprintf("%.1fk", n/1e3); sub(/\.0k$/, "k", s) }
    else               { s = sprintf("%d",     n) }
    return s
}
'
