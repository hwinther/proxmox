# Authelia LDAP bind password (`authelia-ldap-bind`)

Authelia needs a **read-capable service account** on your directory to resolve users and (optionally) groups. The Helm chart mounts Kubernetes Secret **`authelia-ldap-bind`** so the bind password is available at the path Authelia expects (see `spec.values.secret.additionalSecrets` in `authelia-helmrelease.yaml`).

That Secret is **not** stored in Git. Create it on the cluster after **`ldap.user`** in `authelia-helmrelease.yaml` matches your real service-account DN.

LDAP in Git is aligned with **Dovecot** and **SSSD** on this estate:

| SSSD / Dovecot | Authelia (`authelia-helmrelease.yaml`) |
| --- | --- |
| `ldap_uri = ldap://auth.oh.wsh.no` | `ldap.address: ldap://auth.oh.wsh.no:389` |
| `ldap_search_base = dc=oh,dc=wsh,dc=no` | `ldap.base_dn` (same) + `ldap.additional_users_dn: ou=People` (Dovecot `uid=…,ou=People,…`) |
| `ldap_id_use_start_tls = True` | `ldap.start_tls: true` |
| `ldap_tls_reqcert = hard` | `ldap.tls.skip_verify: false` + `ldap.tls.server_name: auth.oh.wsh.no` |
| `ldap_tls_cacert = …/chain.pem` (explicit CA on the host) | **Option 1 (current):** Authelia uses the **container image CA bundle** only — no chart `certificates` block. Matches public chains (e.g. Let’s Encrypt for `auth.oh.wsh.no`). SSSD’s explicit `chain.pem` is not mounted in-cluster unless you later need it for a **private** CA. |

## LDAP TLS trust — option 1 (current)

This deployment **does not** set Helm **`certificates`** / **`certificates.existingSecret`**. LDAP StartTLS verification uses **`ldap.tls.skip_verify: false`** and the **default CA store** in the Authelia image, which is enough when slapd presents a **publicly trusted** certificate for **`auth.oh.wsh.no`**.

**When to add extra trust material:** if Authelia logs TLS errors such as **unknown certificate authority** or **certificate signed by unknown authority**, move to mounting your CA (chart **`certificates.existingSecret`** so Authelia gets `certificates_directory: '/certificates'`) per [Authelia Kubernetes](https://www.authelia.com/integration/deployment/kubernetes/introduction.md). Do not commit PEM files in Git.

**SSSD `auth_provider = krb5`:** SSSD can use Kerberos for host login while still using LDAP for identity. **Authelia’s first factor here is LDAP** (bind + password against the directory). That matches normal “LDAP password” users; it does **not** replace enterprise Kerberos login for Authelia unless you add something like SPNEGO elsewhere.

If your bind account lives outside `ou=People`, change **`ldap.user`** (and optionally **`additional_users_dn`**) accordingly.

## Prerequisites

- `kubectl` configured for the cluster and namespace **`authelia-production`**.
- The bind password as a single line (no trailing newline is ideal).

## Create or replace the Secret

The chart maps the Secret key **`authentication.ldap.password.txt`** to the file name Authelia reads.

**First-time create:**

```bash
kubectl create secret generic authelia-ldap-bind \
  --namespace authelia-production \
  --from-literal=authentication.ldap.password.txt='YOUR_BIND_PASSWORD'
```

**Replace an existing Secret:**

```bash
kubectl delete secret authelia-ldap-bind --namespace authelia-production --ignore-not-found
kubectl create secret generic authelia-ldap-bind \
  --namespace authelia-production \
  --from-literal=authentication.ldap.password.txt='YOUR_BIND_PASSWORD'
```

Optional label:

```bash
kubectl label secret authelia-ldap-bind \
  --namespace authelia-production \
  app.kubernetes.io/name=authelia \
  --overwrite
```

## Reload Authelia

```bash
kubectl rollout restart deployment/authelia --namespace authelia-production
```

## Directory tuning (Git)

In `authelia-helmrelease.yaml`, adjust at least:

| Value | Purpose |
| --- | --- |
| `ldap.address` | **`ldap://auth.oh.wsh.no:389`** (hostname for cert verification) or **`ldaps://…:636`** if you switch to LDAPS |
| `ldap.start_tls` | **`true`** with `ldap://` when the server requires TLS on 389 (Dovecot `tls = yes`) |
| `ldap.tls.server_name` | **`auth.oh.wsh.no`** — should match the name on the LDAP server certificate |
| Helm `certificates` | **Unset (option 1)** — default image CA trust only; add `certificates.existingSecret` if a private CA breaks verification |
| `ldap.implementation` | **`custom`** for OpenLDAP-style trees; use **`activedirectory`** for AD |
| `ldap.user` | Service account bind DN (e.g. **`uid=authelia,ou=services,…`**) |
| `ldap.base_dn` | **`dc=oh,dc=wsh,dc=no`** |
| `ldap.additional_users_dn` | **`ou=People`** (with Dovecot-style `uid=%u,ou=People,…`) |
| `ldap.users_filter` | **`(&(objectClass=inetOrgPerson)({username_attribute}={input}))`** — Authelia **4.39+** requires **`{username_attribute}`** (not `uid={input}` alone) |
| `ldap.groups_filter` | **Required in 4.39+**; here **`(|(&(objectClass=posixGroup)(memberUid={username}))(&(objectClass=groupOfNames)(member={dn})))`** — `posixGroup` / `memberUid` plus **`groupOfNames`** / **`member`** (see [replacements](https://www.authelia.com/integration/ldap/introduction/#groups-filter-replacements)); `member` values must match the user’s real LDAP DN |
| `ldap.additional_groups_dn` | Optional; set (e.g. **`ou=groups`**) to narrow group searches |
| `ldap.attributes.*` | Tune if your schema uses different attribute names |

Dovecot used **client** certs (`tls_cert_file` / `tls_key_file`) to LDAP; Authelia’s chart values here do **not** add client-cert LDAP auth. If slapd requires mTLS for the bind user, you will need a different approach or relax mTLS for that account.

Firewall: allow **Authelia pod egress → `auth.oh.wsh.no`’s resolved IP(s)** on **TCP 389** and/or **636**. `cilium-authelia-egress-ldap.yaml` allows **`10.20.13.202/32`**; update that CIDR if the A record changes.
