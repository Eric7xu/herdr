//! Compare the custom CLI with the pinned official release in isolated sessions.
//! This test makes network requests only on GitHub Actions Unix runners.

#[cfg(unix)]
#[test]
fn custom_and_official_release_interoperate() {
    if std::env::var("GITHUB_ACTIONS").as_deref() != Ok("true") {
        eprintln!("Run scripts/custom_compat.py with --allow-local for an explicit local test");
        return;
    }
    let script = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("scripts/custom_compat.py");
    let status = std::process::Command::new("python3")
        .arg("-I")
        .arg("-B")
        .arg(script)
        .arg("--custom-binary")
        .arg(env!("CARGO_BIN_EXE_herdr"))
        .status()
        .expect("start the isolated compatibility test");
    assert!(
        status.success(),
        "official/custom compatibility test failed"
    );
}
