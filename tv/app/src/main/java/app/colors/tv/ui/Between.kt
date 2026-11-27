package app.colors.tv.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import app.colors.tv.data.Card
import app.colors.tv.data.Profile
import coil3.compose.AsyncImage
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.ceil

private const val COUNTDOWN_MS = 5_000
private const val IDLE_MS = 120_000L

/**
 * Between two videos, when autoplay would play the next one (ADR 0044): what he just watched with Watch again, Up
 * next with a 5-second ring, and a row of more. No key: Up next plays as an autoplay step. Any key stops the ring for
 * good and still does its job; a pick from here is his own, so the chain starts over.
 */
@Composable
fun BetweenScreen(nav: Nav, profile: Profile, played: Card, next: List<Card>, chain: Int) {
    val s = LocalScale.current
    val scope = rememberCoroutineScope()
    val upNext = next.firstOrNull() ?: return LaunchedEffect(Unit) { nav.back() }
    val more = remember(next) { next.drop(1).take(12) }
    var counting by remember { mutableStateOf(true) }
    var lastKey by remember { mutableLongStateOf(System.currentTimeMillis()) }
    val ring = remember { Animatable(0f) }
    val upNextFocus = remember { FocusRequester() }

    // The countdown. A key press sets counting = false, which cancels this and stops the ring where it is.
    LaunchedEffect(counting) {
        if (!counting) return@LaunchedEffect
        ring.animateTo(1f, tween(COUNTDOWN_MS, easing = LinearEasing))
        nav.replace(Screen.Player(profile, upNext.id, chain + 1))
    }
    // Stopped and left alone: back to the rows, so nobody's TV sits on a still picture.
    LaunchedEffect(counting, lastKey) {
        if (counting) return@LaunchedEffect
        delay(IDLE_MS)
        nav.back()
    }
    // A parent ended it, or time ran out while this was up: the Stopped screen, as on the rows.
    val stamp = rememberLimitStamp(nav, profile.id)
    LaunchedEffect(stamp) {
        if (stamp == 0) return@LaunchedEffect
        val t = runCatching { nav.api.home(profile.id).time }.getOrNull() ?: return@LaunchedEffect
        if (!t.open) nav.replace(Screen.Stopped(profile, t))
    }

    fun pick(card: Card, fromStart: Boolean = false) = nav.replace(Screen.Player(profile, card.id, 0, fromStart))

    Box(
        Modifier.fillMaxSize().background(C.Sky).onPreviewKeyEvent { e ->
            if (e.type == KeyEventType.KeyDown) { counting = false; lastKey = System.currentTimeMillis() }
            false  // the key still does its usual job
        },
    ) {
        Scenery()
        Box(Modifier.fillMaxSize().background(Color(0x8C050508)))
        Wordmark(46, Modifier.offset(x = s(1678), y = s(66)))
        Pill("Back", { nav.back() }, Modifier.offset(x = s(96), y = s(63)), icon = Icons.Back)

        // What he just watched.
        Label("You watched", Modifier.offset(x = s(96), y = s(150)))
        Box(Modifier.offset(x = s(96), y = s(240)).size(s(528), s(297)).alpha(.78f).clip(RoundedCornerShape(s(16))).background(Color(0xFF2A2A2A))) {
            AsyncImage(played.thumb, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
            Box(Modifier.align(Alignment.BottomStart).fillMaxWidth().height(s(6)).background(C.Red))
        }
        BasicText(played.title, Modifier.offset(x = s(96), y = s(548)).width(s(528)),
            style = text(34, FontWeight.Bold), maxLines = 1, overflow = TextOverflow.Ellipsis)
        Pill("Watch again", { pick(played, fromStart = true) }, Modifier.offset(x = s(96), y = s(612)), icon = Icons.Restart)

        // Up next, the biggest thing on the screen.
        Label("Up next", Modifier.offset(x = s(840), y = s(110)), on = true)
        Focusable({ pick(upNext) }, Modifier.offset(x = s(828), y = s(168)).size(s(1008), s(600)).focusRequester(upNextFocus)) { focused ->
            Box(Modifier.fillMaxSize().clip(RoundedCornerShape(s(32))).background(if (focused) C.Plate else Color.Transparent))
            Box(Modifier.offset(x = s(12), y = s(12)).size(s(984), s(440)).clip(RoundedCornerShape(s(16))).background(Color(0xFF2A2A2A))) {
                AsyncImage(upNext.thumb, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                Row(
                    Modifier.offset(x = s(24), y = s(24)).height(s(56)).clip(RoundedCornerShape(s(28))).background(Color(0xA8000000)).padding(horizontal = s(22)),
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(s(10)),
                ) {
                    Box(Modifier.size(s(14)).clip(CircleShape).background(C.Sun))
                    BasicText(if (counting) "Plays by itself" else "Pick one", style = text(26, FontWeight.Bold, color = Color.White))
                }
                BasicText(clock(upNext.durationS), Modifier.align(Alignment.BottomEnd).padding(end = s(12), bottom = s(14))
                    .clip(RoundedCornerShape(s(6))).background(Color.Black.copy(alpha = .62f)).padding(horizontal = s(8)),
                    style = text(24, FontWeight.Medium, color = Color.White))
                Countdown(counting, ring.value, Modifier.align(Alignment.Center))
            }
            Column(Modifier.offset(x = s(12), y = s(470)).width(s(984))) {
                BasicText(upNext.title, style = text(46, FontWeight.Bold, playful = true, color = if (focused) C.OnPlate else C.Plate),
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                BasicText("${upNext.containerTitle} · ${clock(upNext.durationS)}", Modifier.padding(top = s(6)),
                    style = text(26, color = if (focused) Color(0xFF4A4950) else C.Muted), maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }

        // More to watch: the rest of /upnext, same channel first.
        if (more.isNotEmpty()) {
            Label("More to watch", Modifier.offset(x = s(96), y = s(782)))
            val rowState = rememberLazyListState()
            val peekPx = with(LocalDensity.current) { s(420).roundToPx() }
            LazyRow(
                Modifier.offset(y = s(822)).fillMaxWidth(), state = rowState,
                contentPadding = PaddingValues(start = s(84), end = s(400)), horizontalArrangement = Arrangement.spacedBy(s(24)),
            ) {
                itemsIndexed(more, key = { _, c -> c.id }) { i, c ->
                    SmallCard(c, { pick(c) }, onFocus = {
                        scope.launch { if (i >= 3) rowState.animateScrollToItem(i - 3, peekPx) else rowState.animateScrollToItem(0) }
                    })
                }
            }
        }
    }
    LaunchedEffect(Unit) { upNextFocus.soon() }
}

@Composable
private fun Label(t: String, modifier: Modifier, on: Boolean = false) =
    BasicText(t.uppercase(), modifier, style = text(34, FontWeight.Bold, color = if (on) C.Plate else C.Muted))

/** The ring around the play button: empties over the countdown, the seconds left in a yellow pill above it. */
@Composable
private fun Countdown(counting: Boolean, done: Float, modifier: Modifier) {
    val s = LocalScale.current
    Box(modifier.size(s(220)), contentAlignment = Alignment.Center) {
        if (counting) Canvas(Modifier.fillMaxSize()) {
            val w = 14 * size.width / 220f
            val inset = w / 2 + 3 * size.width / 220f
            val arc = androidx.compose.ui.geometry.Size(size.width - 2 * inset, size.height - 2 * inset)
            val at = androidx.compose.ui.geometry.Offset(inset, inset)
            drawArc(Color.White.copy(alpha = .28f), 0f, 360f, false, at, arc, style = Stroke(w))
            drawArc(C.Plate, -90f + 360f * done, 360f * (1f - done), false, at, arc, style = Stroke(w, cap = StrokeCap.Round))
        }
        Box(Modifier.size(s(152)).clip(CircleShape).background(C.Red), contentAlignment = Alignment.Center) {
            Icon(Icons.Play, 64, Color.White, filled = true, modifier = Modifier.offset(x = s(6)))
        }
        if (counting) BasicText(
            ceil(5 - done * 5).toInt().coerceIn(1, 5).toString(),
            Modifier.align(Alignment.TopCenter).offset(y = s(-86)).clip(RoundedCornerShape(s(36))).background(C.Sun).padding(horizontal = s(26)),
            style = text(64, FontWeight.Bold, playful = true, color = C.OnPlate),
        )
    }
}

/** A smaller video card for the row: thumbnail 360x203, one line of title. Focused: the light plate. */
@Composable
private fun SmallCard(card: Card, onClick: () -> Unit, onFocus: () -> Unit) {
    val s = LocalScale.current
    Focusable(onClick, Modifier.width(s(384)).height(s(258)), onFocus) { focused ->
        Box(Modifier.fillMaxSize().clip(RoundedCornerShape(s(24))).background(if (focused) C.Plate else Color.Transparent).padding(s(12))) {
            Column {
                Box(Modifier.size(s(360), s(203)).clip(RoundedCornerShape(s(14))).background(Color(0xFF2A2A2A))) {
                    AsyncImage(card.thumb, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                    if (card.watched) Box(Modifier.align(Alignment.BottomStart).fillMaxWidth().height(s(6)).background(C.Red))
                    BasicText(clock(card.durationS), Modifier.align(Alignment.BottomEnd).padding(end = s(10), bottom = s(12))
                        .clip(RoundedCornerShape(s(6))).background(Color.Black.copy(alpha = .62f)).padding(horizontal = s(8)),
                        style = text(22, FontWeight.Medium, color = Color.White))
                }
                BasicText(card.title, Modifier.padding(top = s(8)).width(s(360)),
                    style = text(26, FontWeight.Bold, color = if (focused) C.OnPlate else C.Plate), maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}
