package app.colors.tv.ui

import android.view.KeyEvent as AndroidKey
import androidx.annotation.OptIn
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.nativeKeyCode
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import app.colors.tv.data.Card
import app.colors.tv.data.Play
import app.colors.tv.data.Profile
import app.colors.tv.data.Refused
import app.colors.tv.data.TimeState
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private const val SEEK_MS = 10_000L
private const val HIDE_AFTER_MS = 5_000L

/**
 * The player (reference.md, Player). Nothing shows while a video plays; select shows the title, the bar, Back,
 * play/pause and what plays next. The server is told where we are every heartbeat and may say stop (ADR 0011).
 */
@OptIn(UnstableApi::class)
@Composable
fun PlayerScreen(nav: Nav, profile: Profile, itemId: Int, chain: Int) {
    val s = LocalScale.current
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var play by remember { mutableStateOf<Play?>(null) }
    var time by remember { mutableStateOf<TimeState?>(null) }
    var controls by remember { mutableStateOf(false) }
    var lastKey by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var position by remember { mutableDoubleStateOf(0.0) }
    var duration by remember { mutableDoubleStateOf(0.0) }
    var playing by remember { mutableStateOf(true) }
    var next by remember { mutableStateOf<List<Card>>(emptyList()) }
    var autoplayN by remember { mutableStateOf(2) }
    var finished by remember { mutableStateOf(false) }
    val root = remember { FocusRequester() }
    val playButton = remember { FocusRequester() }

    val player = remember {
        ExoPlayer.Builder(ctx)
            .setMediaSourceFactory(DefaultMediaSourceFactory(OkHttpDataSource.Factory(nav.api.http)))
            .setSeekBackIncrementMs(SEEK_MS).setSeekForwardIncrementMs(SEEK_MS)
            .build()
    }
    val leveler = remember { Leveler(player) }
    DisposableEffect(Unit) { onDispose { leveler.close(); player.release() } }

    // Keep the screen awake while a video plays, or the TV's screensaver comes up over it after its idle timeout
    // (10 min on the office Chromecast, 2026-11-24). Paused, the screensaver may come as usual.
    val view = LocalView.current
    DisposableEffect(playing) {
        view.keepScreenOn = playing
        onDispose { view.keepScreenOn = false }
    }

    fun stopAndShow(t: TimeState?, note: String = "") {
        player.pause()
        nav.replace(Screen.Stopped(profile, t, note))
    }

    // Ask for playback; every rule is checked again on the server at this moment (ADR 0017).
    LaunchedEffect(itemId) {
        val p = try { nav.api.play(profile.id, itemId) } catch (e: Refused) {
            if (e.reason == "closed") return@LaunchedEffect stopAndShow(e.time)
            nav.toast(e.message); return@LaunchedEffect nav.back()
        } catch (e: Exception) {
            nav.toast("The video didn't start. Try another one."); return@LaunchedEffect nav.back()
        }
        play = p; time = p.time
        leveler.apply(p.audio)  // even out the volume before the first sound (ADR 0041)
        player.setMediaItem(MediaItem.fromUri(p.streamUrl))
        player.prepare()
        if (p.resumeS > 1) player.seekTo((p.resumeS * 1000).toLong())
        player.playWhenReady = true
        launch {
            runCatching { nav.api.upNext(profile.id, itemId) }.getOrNull()?.let { (n, cards) -> autoplayN = n; next = cards }
        }
    }

    // Where we are, ten times a second: the bar, and skipping the parts a parent or SponsorBlock marked (ADR 0024).
    LaunchedEffect(play) {
        val p = play ?: return@LaunchedEffect
        while (true) {
            val pos = player.currentPosition / 1000.0
            position = pos
            if (player.duration > 0) duration = player.duration / 1000.0
            playing = player.isPlaying
            p.skip.firstOrNull { pos >= it.startS && pos < it.endS - 0.3 }?.let { player.seekTo((it.endS * 1000).toLong()) }
            if (controls && player.isPlaying && System.currentTimeMillis() - lastKey > HIDE_AFTER_MS) {
                controls = false
                runCatching { root.requestFocus() }
            }
            delay(100)
        }
    }

    // The heartbeat: counts watched time, saves the resume point, may tell us to stop (ADR 0011, ADR 0012).
    LaunchedEffect(play) {
        val p = play ?: return@LaunchedEffect
        while (!finished) {
            delay(p.heartbeatS * 1000L)
            val state = if (player.isPlaying) "playing" else "paused"
            val beat = runCatching { nav.api.heartbeat(profile.id, itemId, player.currentPosition / 1000.0, state) }.getOrNull() ?: continue
            beat.time?.let { time = it; if (it.lastOne) next = emptyList() }  // nothing comes after the last one
            when (beat.command) {
                "stop" -> return@LaunchedEffect stopAndShow(beat.time, if (beat.reason == "parent") "parent" else "")
                "timeup" -> return@LaunchedEffect stopAndShow(beat.time)
            }
        }
    }

    // The end: tell the server, then play what is next while autoplay allows, else back to the rows (ADR 0013).
    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                if (state != Player.STATE_ENDED || finished) return
                finished = true
                scope.launch {
                    val beat = runCatching { nav.api.heartbeat(profile.id, itemId, player.duration / 1000.0, "ended") }.getOrNull()
                    if (beat?.command == "timeup" || beat?.command == "stop") return@launch stopAndShow(beat.time)
                    val upcoming = next.firstOrNull()
                    if (upcoming != null && chain + 1 < autoplayN) nav.replace(Screen.Player(profile, upcoming.id, chain + 1))
                    else nav.back()
                }
            }
        }
        player.addListener(listener)
        onDispose { player.removeListener(listener) }
    }

    fun show() {
        lastKey = System.currentTimeMillis()
        if (!controls) {
            controls = true
            scope.launch { delay(50); runCatching { playButton.requestFocus() } }
        }
    }

    Box(
        Modifier.fillMaxSize().background(Color.Black).focusRequester(root).focusable()
            .onPreviewKeyEvent { e ->
                if (e.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                lastKey = System.currentTimeMillis()
                when (e.key.nativeKeyCode) {
                    AndroidKey.KEYCODE_BACK -> if (controls) { controls = false; runCatching { root.requestFocus() }; true } else {
                        scope.launch { runCatching { nav.api.heartbeat(profile.id, itemId, player.currentPosition / 1000.0, "paused") } }
                        false
                    }
                    AndroidKey.KEYCODE_MEDIA_PLAY_PAUSE, AndroidKey.KEYCODE_MEDIA_PLAY, AndroidKey.KEYCODE_MEDIA_PAUSE -> {
                        if (player.isPlaying) player.pause() else player.play(); show(); true
                    }
                    AndroidKey.KEYCODE_MEDIA_FAST_FORWARD -> { player.seekForward(); show(); true }
                    AndroidKey.KEYCODE_MEDIA_REWIND -> { player.seekBack(); show(); true }
                    AndroidKey.KEYCODE_DPAD_LEFT -> if (!controls) { player.seekBack(); show(); true } else false
                    AndroidKey.KEYCODE_DPAD_RIGHT -> if (!controls) { player.seekForward(); show(); true } else false
                    AndroidKey.KEYCODE_DPAD_CENTER, AndroidKey.KEYCODE_ENTER, AndroidKey.KEYCODE_DPAD_UP, AndroidKey.KEYCODE_DPAD_DOWN ->
                        if (!controls) { show(); true } else false
                    else -> false
                }
            },
    ) {
        AndroidView(
            factory = { c -> PlayerView(c).apply { useController = false; resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT; this.player = player } },
            modifier = Modifier.fillMaxSize(),
        )
        val p = play
        if (p != null && controls) Controls(nav, profile, p.card, time, position, duration, playing, next, playButton,
            onPlayPause = { if (player.isPlaying) player.pause() else player.play(); lastKey = System.currentTimeMillis() },
            onStartOver = { player.seekTo(0); player.play(); lastKey = System.currentTimeMillis() },
            onFocusMove = { lastKey = System.currentTimeMillis() })
        // With the controls up only: the name and a QR code to this child's page for grown-ups. Nothing sits over the
        // picture while it plays, so nothing still can burn into an OLED (Jeff 2026-11-24).
        if (p != null && controls) CornerBadge("${nav.api.server}/admin/#kid/${profile.id}",
            Modifier.align(Alignment.TopEnd).offset(x = -s(40), y = s(40)))
    }
    LaunchedEffect(Unit) { root.soon() }
}

@Composable
private fun Controls(
    nav: Nav, profile: Profile, card: Card, time: TimeState?, position: Double, duration: Double, playing: Boolean,
    next: List<Card>, playButton: FocusRequester, onPlayPause: () -> Unit, onStartOver: () -> Unit, onFocusMove: () -> Unit,
) {
    val s = LocalScale.current
    Box(Modifier.fillMaxSize().background(Color(0xC70B0B0B))) {
        Column(Modifier.offset(x = s(96), y = s(96)).width(s(1100)), verticalArrangement = Arrangement.spacedBy(s(16))) {
            BasicText(card.title, style = text(56, FontWeight.Bold, playful = true).copy(lineHeight = s.sp(72)), maxLines = 2, overflow = TextOverflow.Ellipsis)
            BasicText(card.containerTitle, style = text(24))
        }
        Row(Modifier.align(Alignment.TopEnd).offset(x = -s(BADGE_W + 40 + 32), y = s(96)), horizontalArrangement = Arrangement.spacedBy(s(16)), verticalAlignment = Alignment.CenterVertically) {
            if (time?.lastOne == true) Row(
                Modifier.height(s(64)).clip(RoundedCornerShape(s(32))).background(Color(0xEB1A1A36)).padding(start = s(10), end = s(24)),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(s(12)),
            ) {
                Box(Modifier.size(s(44)).clip(CircleShape).background(C.Sun), contentAlignment = Alignment.Center) {
                    BasicText("1", style = text(32, FontWeight.Bold, playful = true, color = C.Rail))
                }
                BasicText("Last one", style = text(28, FontWeight.Bold))
            }
            if (time != null) TimerPill(time)
        }
        BasicText(clock(position), Modifier.offset(x = s(96), y = s(664)), style = text(22))
        BasicText(clock(duration), Modifier.align(Alignment.TopEnd).offset(x = -s(96), y = s(664)), style = text(22))
        Box(Modifier.offset(x = s(96), y = s(726)).width(s(1728)).height(s(8)).clip(RoundedCornerShape(s(4))).background(Color(0xFF5B5A58))) {
            Box(Modifier.fillMaxWidth(if (duration > 0) (position / duration).toFloat().coerceIn(0f, 1f) else 0f).height(s(8)).background(C.Plate))
        }
        Row(Modifier.offset(x = s(96), y = s(780)), horizontalArrangement = Arrangement.spacedBy(s(20))) {
            Pill("Back", { nav.back() }, icon = Icons.Back, bg = C.PlayerPill)
            Pill("Start over", onStartOver, icon = Icons.Restart, bg = C.PlayerPill)
        }
        Focusable(onPlayPause, Modifier.align(Alignment.TopCenter).offset(y = s(768)).focusRequester(playButton), onFocus = onFocusMove) { focused ->
            Box(
                Modifier.size(s(96)).clip(CircleShape).background(C.Red)
                    .then(if (focused) Modifier.border(s(5), C.Plate, CircleShape) else Modifier.border(s(3), C.Plate.copy(alpha = .6f), CircleShape)),
                contentAlignment = Alignment.Center,
            ) {
                if (playing) Row(horizontalArrangement = Arrangement.spacedBy(s(12))) {
                    repeat(2) { Box(Modifier.width(s(18)).height(s(52)).clip(RoundedCornerShape(s(5))).background(Color.White)) }
                } else Icon(Icons.Play, 52, Color.White, filled = true)
            }
        }
        if (next.isNotEmpty()) Row(Modifier.offset(x = s(84), y = s(885)), horizontalArrangement = Arrangement.spacedBy(s(48))) {
            next.take(3).forEach { c ->
                VideoCard(c, { nav.replace(Screen.Player(profile, c.id)) }, onFocus = onFocusMove)
            }
        }
    }
}

private const val BADGE_W = 168

/** The corner badge, shown with the controls: "colors" over the grown-ups' QR code on a dark card. */
@Composable
private fun CornerBadge(url: String, modifier: Modifier = Modifier) {
    val s = LocalScale.current
    Column(
        modifier.width(s(BADGE_W)).clip(RoundedCornerShape(s(24))).background(Color(0xB30B0B0B)).padding(vertical = s(14)),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(8)),
    ) {
        Wordmark(36)
        QrCard(url, 128, "Grown-ups", labelPx = 18, small = true)
    }
}
