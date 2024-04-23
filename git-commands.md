# Random collection of git snippets

## Start here

```bash
git fetch origin main
git checkout main
git pull
```

git merge --ff-only origin/main
Features - create merge commit (blir +1), squash and merge, eller rebase and merge dersom man har ren historikk via rebranch and update mønster
dev -> test -> qa -> main - løpet må gjøres med KUN via merge commit (øverste knappen) slik at man får med PR'en i historikken, og kan gjøre rebase + push etterpå:

```bash
git checkout qa
git rebase main qa
git push origin qa

git checkout test
git rebase qa test
git push origin test

git checkout dev
git rebase test dev
git push origin dev
```

## meteor

```bash
git checkout test
git rebase main test
git push origin test

git checkout dev
git rebase test dev
git push origin dev
```

## dev (powerapps) conflict resolution

```bash
git checkout main
git branch -D dev-powerapps
git pull
git checkout dev-powerapps
git merge -X ours dev -m "Fix conflicts"
git push origin dev-powerapps
```

## same but for dev -> test

```bash
git checkout main
git branch -D dev
git pull
git checkout dev
git merge -X ours test -m "Fix conflicts"
git push origin dev
```

## same but for test -> qa

```bash
git checkout main
git branch -D test
git pull
git checkout test
git merge -X ours qa -m "Fix conflicts"
git push origin test
```

## same but for qa -> main

```bash
git checkout test
git branch -D qa
git pull
git checkout qa
git merge -X ours main -m "Fix conflicts"
git push origin qa
```

## Slett alle releaser i github

```bash
gh release list | sed -n 's/.*\s\(v[^ ]*\)\s.*/\1/p' | while read line; do gh release delete -y $line; done
```

## Slett alle tags i github

```bash
git tag -d $(git tag -l)
git fetch
git push origin --delete $(git tag -l)
git tag -d $(git tag -l)
```

```bash
git branch | xargs git branch -D
```
