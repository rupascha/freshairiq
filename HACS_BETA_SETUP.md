# FreshAirIQ – HACS Beta Setup

This repository is prepared for installation and updates through HACS as a custom repository.

## One-time setup for the repository owner

1. Create the GitHub repository `rupascha/freshairiq` and upload the complete contents of this repository to its default branch.
2. Keep the repository public while using the normal HACS custom-repository flow.
3. Open the repository's **Actions** tab and make sure GitHub Actions are enabled.
4. The included validation workflows should pass before a release is tagged.
5. Publish the current version by creating and pushing the tag that exactly matches `manifest.json`, prefixed with `v`. For this package that is `v0.25.0.35`.
6. `.github/workflows/release.yml` validates the project and then creates the matching GitHub Release automatically.

Example from a local Git checkout:

```bash
git add .
git commit -m "FreshAirIQ 0.25.0.35"
git push origin main
git tag v0.25.0.35
git push origin v0.25.0.35
```

For every later FreshAirIQ release:

1. Update the version consistently in the project (especially `custom_components/freshairiq/manifest.json`).
2. Commit and push the tested release.
3. Create a matching tag, for example `v0.25.0.38`, and push the tag.
4. Wait for **Publish FreshAirIQ release** to complete successfully.
5. HACS installations can then discover the new release as an update.

Never reuse or move an already published release tag to different code. Create a new version/tag for every hotfix.

## One-time setup for each beta tester

1. Install HACS if it is not already installed.
2. In HACS, open the menu for **Custom repositories**.
3. Add the repository `https://github.com/rupascha/freshairiq` and select the **Integration** category.
4. Find **FreshAirIQ** in HACS and install it.
5. Restart Home Assistant.
6. Open **Settings → Devices & services → Add integration → FreshAirIQ** and complete setup.

After that, testers no longer need to copy the `custom_components/freshairiq` folder for normal releases. When a newer FreshAirIQ release is published, HACS can surface it as an available update. Home Assistant should be restarted when HACS requests it after an integration update.

## Beta release discipline

For the first external installations, keep releases small and reversible. Publish only versions that passed the repository validation. If a regression is found, fix it in a new version rather than replacing an existing GitHub Release or tag. This makes every tester installation traceable to an exact FreshAirIQ version.
