// imagegen: prompt + N -> Gemini (Nano Banana 2) -> images in a temp dir -> open in Preview.
// Native macOS; Cmd+C in Preview copies the selected image.
//
// Usage:   imagegen "a fox in a spacesuit" [N] [--aspect 1:1|16:9|9:16|4:3|3:4]
//          imagegen --selftest          (no API call; checks decode+write)
//
// Key:     GEMINI_API_KEY env, else first line of ~/.config/gemini-key
// Model:   gemini-3.1-flash-image-preview returns ONE image per call, so N options = N calls.

use base64::{engine::general_purpose::STANDARD, Engine};
use std::fs;
use std::path::PathBuf;
use std::process::Command;

const MODEL: &str = "gemini-3.1-flash-image-preview";

fn url() -> String {
    format!("https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent")
}

fn die(msg: &str) -> ! {
    eprintln!("imagegen: {msg}");
    std::process::exit(1);
}

fn api_key() -> String {
    if let Ok(k) = std::env::var("GEMINI_API_KEY") {
        if !k.trim().is_empty() {
            return k.trim().to_string();
        }
    }
    let home = std::env::var("HOME").unwrap_or_default();
    let path = PathBuf::from(home).join(".config/gemini-key");
    match fs::read_to_string(&path) {
        Ok(s) => s.lines().next().unwrap_or("").trim().to_string(),
        Err(_) => die("no API key. Set GEMINI_API_KEY or put it in ~/.config/gemini-key"),
    }
}

fn slug(prompt: &str) -> String {
    let s: String = prompt
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
        .collect();
    let s = s.trim_matches('-').to_lowercase();
    let s: String = s.chars().take(30).collect();
    let s = s.trim_matches('-').to_string();
    if s.is_empty() { "image".to_string() } else { s }
}

fn ext_for(mime: &str) -> &'static str {
    if mime.contains("png") { "png" } else if mime.contains("webp") { "webp" } else { "jpg" }
}

// One Gemini call -> (base64 bytes, mime). Returns None if the model returned no image
// (e.g. a safety refusal, which comes back as a text part instead).
fn one_image(key: &str, prompt: &str, aspect: &Option<String>) -> Option<(String, String)> {
    let mut cfg = serde_json::json!({ "responseModalities": ["IMAGE"] });
    if let Some(a) = aspect {
        cfg["imageConfig"] = serde_json::json!({ "aspectRatio": a });
    }
    let body = serde_json::json!({
        "contents": [{ "parts": [{ "text": prompt }] }],
        "generationConfig": cfg,
    });

    let resp = ureq::post(&url())
        .set("x-goog-api-key", key)
        .set("Content-Type", "application/json")
        .send_json(body);

    let json: serde_json::Value = match resp {
        Ok(r) => r.into_json().unwrap_or_else(|e| die(&format!("bad JSON: {e}"))),
        Err(ureq::Error::Status(code, r)) => {
            die(&format!("API {code}: {}", r.into_string().unwrap_or_default()))
        }
        Err(e) => die(&format!("request failed: {e}")),
    };

    let parts = json["candidates"][0]["content"]["parts"].as_array()?;
    for p in parts {
        if let Some(data) = p["inlineData"]["data"].as_str() {
            let mime = p["inlineData"]["mimeType"].as_str().unwrap_or("image/jpeg").to_string();
            return Some((data.to_string(), mime));
        }
    }
    None
}

fn write_image(dir: &std::path::Path, base: &str, i: usize, b64: &str, mime: &str) -> PathBuf {
    let bytes = STANDARD.decode(b64.trim()).unwrap_or_else(|e| die(&format!("base64 decode: {e}")));
    let p = dir.join(format!("{base}-{}.{}", i + 1, ext_for(mime)));
    fs::write(&p, &bytes).unwrap_or_else(|e| die(&format!("write: {e}")));
    p
}

fn selftest() {
    // 1x1 PNG, base64  -  exercises decode + write + temp dir, no network.
    let png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";
    let dir = std::env::temp_dir().join(format!("imagegen-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    let p = write_image(&dir, "selftest", 0, png, "image/png");
    let meta = fs::metadata(&p).expect("file must exist");
    assert!(meta.len() > 0, "file must be non-empty");
    let _ = fs::remove_file(&p);
    println!("selftest ok: wrote {} ({} bytes)", p.display(), meta.len());
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--selftest") {
        selftest();
        return;
    }
    if args.is_empty() || args[0] == "-h" || args[0] == "--help" {
        eprintln!("usage: imagegen \"prompt\" [N] [--aspect 1:1|16:9|9:16|4:3|3:4]");
        std::process::exit(if args.is_empty() { 1 } else { 0 });
    }

    let prompt = args[0].clone();
    let mut n: u32 = 4;
    let mut aspect: Option<String> = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--aspect" => { i += 1; aspect = args.get(i).cloned(); }
            other => { if let Ok(v) = other.parse::<u32>() { n = v; } }
        }
        i += 1;
    }
    n = n.clamp(1, 10);

    let key = api_key();
    let dir = std::env::temp_dir().join(format!("imagegen-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap_or_else(|e| die(&format!("mkdir: {e}")));
    let base = slug(&prompt);

    let mut paths = Vec::new();
    for idx in 0..n as usize {
        eprintln!("imagegen: {MODEL} option {}/{n}...", idx + 1);
        match one_image(&key, &prompt, &aspect) {
            Some((b64, mime)) => paths.push(write_image(&dir, &base, idx, &b64, &mime)),
            None => eprintln!("imagegen: option {} returned no image (likely a safety refusal), skipping", idx + 1),
        }
    }

    if paths.is_empty() {
        die("no images produced");
    }
    for p in &paths {
        println!("{}", p.display());
    }
    let _ = Command::new("open").arg("-a").arg("Preview").args(&paths).status();
}
