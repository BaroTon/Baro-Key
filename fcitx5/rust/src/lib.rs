//! BARO typing core.
//!
//! The Vietnamese transformations come from [`bamboo_core`], the same Rust
//! engine used by Ngó Sen.  This crate only adds the small state machine that
//! an input-method shell needs: per-context buffers, invalid-word restoration
//! and a C ABI for the Fcitx5 addon.

use std::collections::BTreeMap;
use std::ffi::{c_char, CStr};
use std::sync::{Mutex, MutexGuard};

use bamboo_core::{
    BracketMode, Config, Engine, InputMethod, Mode, ToneStyle, W2uMode,
};

const KEY_BACKSPACE: u32 = 0xff08;
const KEY_TAB: u32 = 0xff09;
const KEY_RETURN: u32 = 0xff0d;
const KEY_KP_ENTER: u32 = 0xff8d;

struct Baro {
    engine: Engine,
    method: String,
    modern_style: bool,
    free_marking: bool,
    auto_restore: bool,
    enabled: bool,
    commit: String,
}

impl Baro {
    fn new(method: &str) -> Self {
        let method = normalize_method(method);
        Self {
            engine: make_engine(&method, true, true, true),
            method,
            modern_style: true,
            free_marking: true,
            auto_restore: true,
            enabled: true,
            commit: String::new(),
        }
    }

    fn config(&self) -> Config {
        Config::builder()
            .free_tone_marking(self.free_marking)
            // BARO calls "modern" the hoà/thuỷ placement; bamboo-core calls
            // that Traditional and its Modern is hòa/thuỷ.
            .tone_style(if self.modern_style {
                ToneStyle::Traditional
            } else {
                ToneStyle::Modern
            })
            .auto_correct(self.auto_restore)
            .w2u_mode(W2uMode::Everywhere)
            .bracket_mode(BracketMode::Everywhere)
            .build()
    }

    fn rebuild(&mut self) {
        self.engine = make_engine(
            &self.method,
            self.modern_style,
            self.free_marking,
            self.auto_restore,
        );
    }

    fn display(&self) -> String {
        // bamboo-core's auto_correct restore already handles invalid words,
        // including partially Vietnamese ones like "đow"; a second filter
        // here would turn those back into their full raw keys.
        self.engine.output().into_owned()
    }

    fn commit_display(&self) -> String {
        self.engine.output().into_owned()
    }

    fn push_commit(&mut self, text: &str) {
        self.commit.push_str(text);
    }

    fn clear(&mut self) {
        self.engine.reset();
    }

    fn flush(&mut self) {
        let text = self.commit_display();
        if !text.is_empty() {
            self.push_commit(&text);
        }
        self.clear();
    }

    fn accepts(&self, ch: char) -> bool {
        if ch.is_ascii_alphabetic() {
            return true;
        }
        if ch == '[' || ch == ']' {
            return self.method != "vni";
        }
        if ch.is_ascii_digit() {
            return self.method == "vni" && !self.display().is_empty();
        }
        false
    }

    fn process_key(&mut self, keyval: u32) -> bool {
        if !self.enabled {
            return false;
        }
        if keyval == KEY_BACKSPACE {
            if self.display().is_empty() {
                return false;
            }
            // Drop the last output grapheme and keep the marks on the letters
            // before it, so "việt" backspaces to "việ" rather than replaying
            // the raw keys (which would move the tone to "vịê").
            self.engine.remove_last_output_char();
            return true;
        }
        let Some(ch) = char::from_u32(keyval) else {
            return false;
        };
        if matches!(ch, ' ' | '\t' | '\n' | '\r') || keyval == KEY_TAB || keyval == KEY_RETURN || keyval == KEY_KP_ENTER {
            return false;
        }
        if !self.accepts(ch) {
            // A key that ends the word (punctuation, a digit in Telex, an
            // unsupported letter) commits what was typed before it.
            self.flush();
            return false;
        }
        self.engine.process_key(ch, Mode::Vietnamese);
        true
    }
}

fn normalize_method(method: &str) -> String {
    if method.eq_ignore_ascii_case("vni") {
        "vni".to_string()
    } else {
        "telex".to_string()
    }
}

fn make_engine(method: &str, modern_style: bool, free_marking: bool, auto_restore: bool) -> Engine {
    let input_method = if method == "vni" {
        InputMethod::vni()
    } else {
        InputMethod::telex()
    };
    let config = Config::builder()
        .free_tone_marking(free_marking)
        .tone_style(if modern_style {
            ToneStyle::Traditional
        } else {
            ToneStyle::Modern
        })
        .auto_correct(auto_restore)
        .w2u_mode(W2uMode::Everywhere)
        .bracket_mode(BracketMode::Everywhere)
        .build();
    Engine::with_config(input_method, config)
}

fn registry() -> MutexGuard<'static, BTreeMap<usize, Baro>> {
    static REGISTRY: Mutex<BTreeMap<usize, Baro>> = Mutex::new(BTreeMap::new());
    REGISTRY.lock().unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn with_baro<R>(handle: usize, f: impl FnOnce(&mut Baro) -> R) -> Option<R> {
    registry().get_mut(&handle).map(f)
}

fn string_from_c(text: *const c_char) -> String {
    if text.is_null() {
        return String::new();
    }
    // SAFETY: the caller promises a NUL-terminated string.
    unsafe { CStr::from_ptr(text) }.to_string_lossy().into_owned()
}

fn c_string(text: &str) -> *mut c_char {
    // SAFETY: the allocation has room for the bytes and the trailing NUL.
    unsafe {
        let raw = libc::malloc(text.len() + 1).cast::<u8>();
        if raw.is_null() {
            return std::ptr::null_mut();
        }
        std::ptr::copy_nonoverlapping(text.as_ptr(), raw, text.len());
        *raw.add(text.len()) = 0;
        raw.cast()
    }
}

/// Creates an engine for `method` ("telex" or "vni").  Returns 0 on failure.
///
/// # Safety
/// `method` is null or a NUL-terminated string.
#[no_mangle]
pub unsafe extern "C" fn baro_engine_new(method: *const c_char) -> usize {
    let method = string_from_c(method);
    let engine = Baro::new(&method);
    let mut reg = registry();
    let handle = if reg.is_empty() { 1 } else { *reg.keys().next_back().unwrap() + 1 };
    reg.insert(handle, engine);
    handle
}

#[no_mangle]
pub extern "C" fn baro_engine_free(handle: usize) {
    registry().remove(&handle);
}

#[no_mangle]
pub extern "C" fn baro_engine_set_options(
    handle: usize,
    modern_style: bool,
    free_marking: bool,
    auto_restore: bool,
) {
    with_baro(handle, |baro| {
        if baro.modern_style == modern_style
            && baro.free_marking == free_marking
            && baro.auto_restore == auto_restore
        {
            return;
        }
        baro.modern_style = modern_style;
        baro.free_marking = free_marking;
        baro.auto_restore = auto_restore;
        let config = baro.config();
        baro.engine.set_config(config);
    });
}

/// # Safety
/// `method` is null or a NUL-terminated string.
#[no_mangle]
pub unsafe extern "C" fn baro_engine_set_method(handle: usize, method: *const c_char) {
    let method = string_from_c(method);
    with_baro(handle, |baro| {
        let method = normalize_method(&method);
        if baro.method == method {
            return;
        }
        baro.flush();
        baro.method = method;
        baro.rebuild();
    });
}

#[no_mangle]
pub extern "C" fn baro_engine_set_enabled(handle: usize, enabled: bool) {
    with_baro(handle, |baro| {
        if baro.enabled == enabled {
            return;
        }
        if !enabled {
            baro.flush();
        }
        baro.enabled = enabled;
    });
}

#[no_mangle]
pub extern "C" fn baro_engine_enabled(handle: usize) -> bool {
    with_baro(handle, |baro| baro.enabled).unwrap_or(false)
}

#[no_mangle]
pub extern "C" fn baro_engine_process_key(handle: usize, keyval: u32) -> bool {
    with_baro(handle, |baro| baro.process_key(keyval)).unwrap_or(false)
}

/// Removes the last output grapheme, keeping marks on the earlier letters.
/// Returns false when there is nothing to delete.
#[no_mangle]
pub extern "C" fn baro_engine_backspace(handle: usize) -> bool {
    with_baro(handle, |baro| {
        if baro.display().is_empty() {
            return false;
        }
        baro.engine.remove_last_output_char();
        true
    })
    .unwrap_or(false)
}

#[no_mangle]
pub extern "C" fn baro_engine_pull_preedit(handle: usize) -> *mut c_char {
    let text = with_baro(handle, |baro| baro.display()).unwrap_or_default();
    c_string(&text)
}

#[no_mangle]
pub extern "C" fn baro_engine_pull_commit(handle: usize) -> *mut c_char {
    let text = with_baro(handle, |baro| std::mem::take(&mut baro.commit)).unwrap_or_default();
    c_string(&text)
}

#[no_mangle]
pub extern "C" fn baro_engine_commit(handle: usize) {
    with_baro(handle, |baro| baro.flush());
}

#[no_mangle]
pub extern "C" fn baro_engine_reset(handle: usize) {
    with_baro(handle, |baro| {
        baro.clear();
        baro.commit.clear();
    });
}

/// # Safety
/// `text` must be a pointer returned by one of the `baro_engine_pull_*`
/// functions, or null.
#[no_mangle]
pub unsafe extern "C" fn baro_engine_string_free(text: *mut c_char) {
    if !text.is_null() {
        // SAFETY: the pointer came from libc::malloc in c_string.
        unsafe { libc::free(text.cast()) };
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pull(handle: usize) -> String {
        let pointer = baro_engine_pull_preedit(handle);
        // SAFETY: the pointer is a valid string from the engine.
        let text = unsafe { CStr::from_ptr(pointer) }.to_string_lossy().into_owned();
        // SAFETY: the pointer was allocated by the engine.
        unsafe { baro_engine_string_free(pointer) };
        text
    }

    fn pull_commit(handle: usize) -> String {
        let pointer = baro_engine_pull_commit(handle);
        // SAFETY: the pointer is a valid string from the engine.
        let text = unsafe { CStr::from_ptr(pointer) }.to_string_lossy().into_owned();
        // SAFETY: the pointer was allocated by the engine.
        unsafe { baro_engine_string_free(pointer) };
        text
    }

    fn type_keys(handle: usize, keys: &str) {
        for key in keys.chars() {
            assert!(baro_engine_process_key(handle, key as u32));
        }
    }

    #[test]
    fn telex_word() {
        let handle = unsafe { baro_engine_new(b"telex\0".as_ptr().cast()) };
        type_keys(handle, "vieejt");
        assert_eq!(pull(handle), "việt");
        baro_engine_commit(handle);
        assert_eq!(pull_commit(handle), "việt");
        assert_eq!(pull(handle), "");
        baro_engine_free(handle);
    }

    #[test]
    fn vni_word() {
        let handle = unsafe { baro_engine_new(b"vni\0".as_ptr().cast()) };
        type_keys(handle, "vie6t5");
        assert_eq!(pull(handle), "việt");
        baro_engine_commit(handle);
        assert_eq!(pull_commit(handle), "việt");
        baro_engine_free(handle);
    }

    #[test]
    fn invalid_word_restores_raw_keys() {
        let handle = unsafe { baro_engine_new(b"telex\0".as_ptr().cast()) };
        type_keys(handle, "asd");
        assert_eq!(pull(handle), "asd");
        baro_engine_commit(handle);
        assert_eq!(pull_commit(handle), "asd");
        baro_engine_free(handle);
    }

    #[test]
    fn tone_style() {
        let handle = unsafe { baro_engine_new(b"telex\0".as_ptr().cast()) };
        baro_engine_set_options(handle, true, true, true);
        type_keys(handle, "hoaf");
        assert_eq!(pull(handle), "hoà");
        baro_engine_reset(handle);
        baro_engine_set_options(handle, false, true, true);
        type_keys(handle, "hoaf");
        assert_eq!(pull(handle), "hòa");
        baro_engine_free(handle);
    }

    #[test]
    fn backspace_removes_display_char() {
        let handle = unsafe { baro_engine_new(b"telex\0".as_ptr().cast()) };
        type_keys(handle, "vieejt");
        assert!(baro_engine_process_key(handle, KEY_BACKSPACE));
        // bamboo-core keeps the tone on the earlier vowel once the final
        // consonant is gone, matching Ngó Sen's preedit backspace.
        assert_eq!(pull(handle), "vịê");
        for _ in 0..3 {
            assert!(baro_engine_process_key(handle, KEY_BACKSPACE));
        }
        assert_eq!(pull(handle), "");
        baro_engine_free(handle);
    }

    #[test]
    fn disabled_passes_keys() {
        let handle = unsafe { baro_engine_new(b"telex\0".as_ptr().cast()) };
        type_keys(handle, "vieejt");
        baro_engine_set_enabled(handle, false);
        assert_eq!(pull_commit(handle), "việt");
        assert!(!baro_engine_process_key(handle, 'a' as u32));
        assert_eq!(pull(handle), "");
        baro_engine_free(handle);
    }

    #[test]
    fn uppercase_is_preserved() {
        let handle = unsafe { baro_engine_new(b"telex\0".as_ptr().cast()) };
        type_keys(handle, "VIEEJT");
        assert_eq!(pull(handle), "VIỆT");
        baro_engine_free(handle);
    }
}
