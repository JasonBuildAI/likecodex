use anyhow::{Context, Result};
use reqwest::Client;
use semver::Version;
use serde::Deserialize;
use tracing::info;

const CURRENT_VERSION: &str = env!("CARGO_PKG_VERSION");
const REPO_OWNER: &str = "JasonBuildAI";
const REPO_NAME: &str = "likecodex";

/// GitHub Release asset information.
#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct GithubRelease {
    tag_name: String,
    #[serde(default)]
    prerelease: bool,
    #[serde(default)]
    body: String,
}

/// Check for newer LikeCodex releases on GitHub.
pub async fn check_for_updates(client: &Client) -> Result<Option<String>> {
    let url = format!(
        "https://api.github.com/repos/{}/{}/releases/latest",
        REPO_OWNER, REPO_NAME
    );

    info!("Checking for updates at {url}");

    let resp = client
        .get(&url)
        .header("User-Agent", "likecodex-cli")
        .header("Accept", "application/vnd.github.v3+json")
        .send()
        .await
        .context("Failed to reach GitHub Releases API")?;

    if !resp.status().is_success() {
        return Ok(None); // Rate-limited or offline — silent skip
    }

    let release: GithubRelease = resp
        .json()
        .await
        .context("Failed to parse GitHub release response")?;

    let remote_tag = release.tag_name.trim_start_matches('v');
    let current = Version::parse(CURRENT_VERSION).unwrap_or(Version::new(0, 0, 0));
    let remote = match Version::parse(remote_tag) {
        Ok(v) => v,
        Err(_) => return Ok(None),
    };

    if remote > current {
        Ok(Some(release.tag_name))
    } else {
        Ok(None) // Up to date
    }
}

/// Run the update check and print results.
pub async fn cmd_update(client: &Client, auto_install: bool) -> Result<()> {
    println!("LikeCodex v{CURRENT_VERSION}");
    println!("Checking for updates...");

    match check_for_updates(client).await {
        Ok(Some(version)) => {
            println!(
                "[update] New version available: {version} (current: v{CURRENT_VERSION})"
            );
            println!(
                "[update] Download: https://github.com/{}/{}/releases/tag/{version}",
                REPO_OWNER, REPO_NAME
            );

            if auto_install {
                println!("[update] Auto-install triggered...");
                let status = std::process::Command::new("cargo")
                    .args([
                        "install",
                        "--git",
                        &format!("https://github.com/{}/{}.git", REPO_OWNER, REPO_NAME),
                        "--tag",
                        &version,
                        "likecodex-cli",
                    ])
                    .status()
                    .context("Failed to run cargo install")?;

                if status.success() {
                    println!("[update] Upgraded to {version}. Please restart.");
                } else {
                    anyhow::bail!("cargo install failed with status {status:?}");
                }
            }
        }
        Ok(None) => {
            println!("[update] You are on the latest version (v{CURRENT_VERSION}).");
        }
        Err(e) => {
            println!("[update] Check failed: {e}");
            println!("[update] You can manually check at https://github.com/{}/{}/releases", REPO_OWNER, REPO_NAME);
        }
    }

    Ok(())
}
