package app.colors.tv.ui

import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import app.colors.tv.data.Card
import app.colors.tv.data.Profile
import app.colors.tv.data.TimeState
import coil3.compose.AsyncImage
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel

// ---- scenery ----------------------------------------------------------------------------------------------------------

/** The sky, clouds, purple hills and ground behind the home screen. It stays still while rows move. */
@Composable
fun Scenery(dim: Boolean = false, modifier: Modifier = Modifier.fillMaxSize()) {
    Canvas(modifier) {
        val k = size.width / 1920f
        val sky = if (dim) C.DimSky else C.Sky
        val ground = if (dim) C.DimGround else C.Ground
        val hills = if (dim) Color(0xFF3A0A52) else C.Hills
        val cloud = if (dim) Color(0xFF1C1C20) else C.Cloud
        drawRect(sky)
        fun cloud(x: Float, y: Float, s: Float) {
            for ((dx, dy, rx, ry) in listOf(
                listOf(0f, 0f, 70f, 26f), listOf(-40f, -14f, 38f, 26f), listOf(20f, -24f, 46f, 32f), listOf(62f, -8f, 32f, 20f),
            )) drawOval(cloud, Offset((x + (dx - rx) * s) * k, (y + (dy - ry) * s) * k), Size(2 * rx * s * k, 2 * ry * s * k))
        }
        cloud(1044f, 56f, 1f); cloud(1556f, 140f, 1.5f); cloud(910f, 490f, .5f); cloud(1700f, 426f, .32f)
        val left = Path().apply {
            moveTo(0f, 700 * k); cubicTo(60 * k, 690 * k, 110 * k, 690 * k, 156 * k, 700 * k)
            cubicTo(240 * k, 650 * k, 300 * k, 610 * k, 420 * k, 624 * k)
            cubicTo(520 * k, 600 * k, 600 * k, 640 * k, 700 * k, 668 * k)
            cubicTo(780 * k, 690 * k, 840 * k, 700 * k, 900 * k, 720 * k)
            lineTo(0f, 720 * k); close()
        }
        val right = Path().apply {
            moveTo(1384 * k, 720 * k); cubicTo(1480 * k, 690 * k, 1560 * k, 690 * k, 1640 * k, 668 * k)
            cubicTo(1740 * k, 640 * k, 1820 * k, 628 * k, 1920 * k, 632 * k); lineTo(1920 * k, 720 * k); close()
        }
        drawPath(left, hills); drawPath(right, hills)
        val dot = Color(0xFFC6E014).copy(alpha = if (dim) .35f else .9f)
        for ((x, y) in listOf(178f to 613f, 522f to 634f, 664f to 650f, 1846f to 607f, 1560f to 640f)) drawCircle(dot, 3 * k, Offset(x * k, y * k))
        drawRect(ground, Offset(0f, 718 * k), Size(size.width, size.height - 718 * k))
    }
}

// ---- the name ---------------------------------------------------------------------------------------------------------

@Composable
fun Wordmark(px: Int = 60, modifier: Modifier = Modifier) {
    val word: AnnotatedString = buildAnnotatedString {
        "colors".forEachIndexed { i, ch -> withStyle(SpanStyle(color = C.Letters[i])) { append(ch) } }
    }
    BasicText(word, modifier, style = text(px, FontWeight.Bold, playful = true))
}

// ---- icons (stroke paths on a 24 grid) --------------------------------------------------------------------------------

object Icons {
    const val Home = "M12 3.2l8.6 7.6h-2.3v9.4h-4.6v-6.2h-3.4v6.2H5.7v-9.4H3.4z"
    const val Lock = "M7 10.5h10a2 2 0 0 1 2 2v6a2 2 0 0 1 -2 2h-10a2 2 0 0 1 -2 -2v-6a2 2 0 0 1 2 -2zM8 10.5V7.8a4 4 0 0 1 8 0v2.7"
    const val Back = "M19 12H5.5M11 6l-6 6 6 6"
    const val Play = "M8 5.5v13l11-6.5z"
    const val Speaker = "M4 9.5v5h3.5l5 4v-13l-5 4zM16 9a4.5 4.5 0 0 1 0 6M18.8 6.5a8.5 8.5 0 0 1 0 11"
    const val Channels = "M4.5 7h15a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1 -1.5 1.5h-15a1.5 1.5 0 0 1 -1.5 -1.5v-9a1.5 1.5 0 0 1 1.5 -1.5zM8.5 3l3.5 3.5 3.5-3.5"
    const val Recent = "M4.3 12a7.7 7.7 0 1 0 2.25-5.45M4.3 3.6v3.3h3.3M12 8v4.3l2.9 1.8"
    const val Star = "M12 3.6l2.55 5.2 5.75.83-4.15 4.05.98 5.72-5.13-2.7-5.13 2.7.98-5.72-4.15-4.05 5.75-.83z"
    const val New = "M12 2.8v5M12 16.2v5M2.8 12h5M16.2 12h5M5.5 5.5l3.3 3.3M15.2 15.2l3.3 3.3M5.5 18.5l3.3-3.3M15.2 8.8l3.3-3.3"
    const val Search = "M10.5 4a6.5 6.5 0 1 1 0 13a6.5 6.5 0 0 1 0 -13zM15.4 15.4L20 20"
    const val Restart = "M5 12a7 7 0 1 0 2.05-4.95M5 4v3.6h3.6"
}

@Composable
fun Icon(path: String, px: Int, color: Color = C.Plate, filled: Boolean = false, modifier: Modifier = Modifier) {
    val s = LocalScale.current
    val shape = remember(path) { PathParser().parsePathString(path).toPath() }
    Canvas(modifier.size(s(px))) {
        val k = size.width / 24f
        scale(k, k, pivot = Offset.Zero) {
            if (filled) drawPath(shape, color) else drawPath(shape, color, style = Stroke(width = 2.2f, cap = StrokeCap.Round))
        }
    }
}

// ---- focus -----------------------------------------------------------------------------------------------------------

/** Give the remote's focus to something once the screen has drawn (asking on the first frame can be too early). */
suspend fun FocusRequester.soon() {
    repeat(10) {
        kotlinx.coroutines.delay(60)
        if (runCatching { requestFocus() }.isSuccess) return
    }
}

/** A focusable, clickable thing that knows whether it has the focus. */
@Composable
fun Focusable(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    onFocus: () -> Unit = {},
    content: @Composable BoxScope.(focused: Boolean) -> Unit,
) {
    val source = remember { MutableInteractionSource() }
    val focused by source.collectIsFocusedAsState()
    androidx.compose.runtime.LaunchedEffect(focused) { if (focused) onFocus() }
    Box(modifier.clickable(interactionSource = source, indication = null, onClick = onClick)) { content(focused) }
}

// ---- cards -----------------------------------------------------------------------------------------------------------

/**
 * A video card: thumbnail 528x297, a two-line title. Focused: a light plate 12 px past the thumbnail and down past
 * the title, dark title text. Nothing grows or moves (reference.md, Home).
 */
@Composable
fun VideoCard(card: Card, onClick: () -> Unit, modifier: Modifier = Modifier, onFocus: () -> Unit = {}, lengthText: String? = null) {
    val s = LocalScale.current
    Focusable(onClick, modifier.width(s(552)).height(s(426)), onFocus) { focused ->
        Box(
            Modifier.fillMaxSize().clip(RoundedCornerShape(s(28)))
                .background(if (focused) C.Plate else Color.Transparent).padding(s(12)),
        ) {
            Column {
                Box(Modifier.width(s(528)).height(s(297)).clip(RoundedCornerShape(s(16))).background(Color(0xFF2A2A2A))) {
                    AsyncImage(card.thumb, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                    val seen = when {
                        card.watched -> 1f
                        card.durationS > 0 && card.positionS > 0 -> (card.positionS / card.durationS).toFloat().coerceIn(0f, 1f)
                        else -> 0f
                    }
                    if (seen > 0f) {
                        Box(Modifier.align(Alignment.BottomStart).fillMaxWidth().height(s(6)).background(Color.White.copy(alpha = .35f)))
                        Box(Modifier.align(Alignment.BottomStart).fillMaxWidth(seen).height(s(6)).background(C.Red))
                    }
                    BasicText(
                        lengthText ?: clock(card.durationS),
                        Modifier.align(Alignment.BottomEnd).padding(end = s(12), bottom = s(14))
                            .clip(RoundedCornerShape(s(6))).background(Color.Black.copy(alpha = .62f)).padding(horizontal = s(8)),
                        style = text(24, FontWeight.Medium, color = Color.White),
                    )
                }
                BasicText(
                    card.title, Modifier.padding(top = s(14)).width(s(528)),
                    style = text(34, FontWeight.Bold, color = if (focused) C.OnPlate else C.Plate).copy(lineHeight = s.sp(48)),
                    maxLines = 2, overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

fun clock(seconds: Double): String {
    val t = seconds.toLong().coerceAtLeast(0)
    val h = t / 3600; val m = (t % 3600) / 60; val sec = t % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, sec) else "%d:%02d".format(m, sec)
}

// ---- profile pictures ------------------------------------------------------------------------------------------------

@Composable
fun Avatar(p: Profile, px: Int, modifier: Modifier = Modifier) {
    val s = LocalScale.current
    Box(modifier.size(s(px)).clip(CircleShape).background(C.avatar(p.avatarColor)), contentAlignment = Alignment.Center) {
        if (p.avatarUrl != null) AsyncImage(p.avatarUrl, null, Modifier.fillMaxSize(), contentScale = ContentScale.Fit)
        else BasicText(p.name.take(1).uppercase(), style = text(px * .45f, FontWeight.Bold, playful = true, color = Color(0xFF1D2430)))
    }
}

// ---- the timer -------------------------------------------------------------------------------------------------------

/** A ring and the minutes left, top right by the name. Only when a limit runs and the parent turned the timer on. */
@Composable
fun TimerPill(time: TimeState, modifier: Modifier = Modifier) {
    val left = time.leftS ?: return
    if (!time.limited || !time.showTimer) return
    val s = LocalScale.current
    val mins = kotlin.math.ceil(left / 60).toInt().coerceAtLeast(0)
    val frac = (left / (60 * 60)).toFloat().coerceIn(0.04f, 1f)
    val ring = if (mins <= 10) C.Orange else C.Sun
    Row(
        modifier.height(s(64)).clip(RoundedCornerShape(s(32))).background(Color(0xEB1A1A36)).padding(start = s(10), end = s(22)),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(s(12)),
    ) {
        Canvas(Modifier.size(s(44))) {
            val w = 7f * size.width / 44f
            drawArc(Color(0xFF3B3A66), 0f, 360f, false, Offset(w / 2, w / 2), Size(size.width - w, size.height - w), style = Stroke(w))
            drawArc(ring, -90f, 360f * frac, false, Offset(w / 2, w / 2), Size(size.width - w, size.height - w), style = Stroke(w, cap = StrokeCap.Round))
        }
        BasicText("$mins min", style = text(28, FontWeight.Bold))
    }
}

// ---- QR codes (ADR 0039) ---------------------------------------------------------------------------------------------

/** A QR code on a white card, so a parent's phone camera opens the parents' page at the right place. */
@Composable
fun QrCard(url: String, px: Int, label: String, modifier: Modifier = Modifier, labelPx: Int = 26, small: Boolean = false) {
    val s = LocalScale.current
    val matrix = remember(url) {
        QRCodeWriter().encode(url, BarcodeFormat.QR_CODE, 0, 0, mapOf(EncodeHintType.ERROR_CORRECTION to (if (small) ErrorCorrectionLevel.L else ErrorCorrectionLevel.M), EncodeHintType.MARGIN to 1))
    }
    Column(modifier.width(s(px)), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(if (small) 8 else 14))) {
        Canvas(Modifier.size(s(px)).clip(RoundedCornerShape(s(24))).background(Color.White).padding(s(px * .05f))) {
            val n = matrix.width
            val cell = size.width / n
            for (y in 0 until n) for (x in 0 until n) if (matrix[x, y]) {
                drawRect(C.Rail, Offset(x * cell, y * cell), Size(cell + .6f, cell + .6f))
            }
        }
        BasicText(label, style = text(labelPx, FontWeight.Bold).copy(textAlign = TextAlign.Center))
    }
}

// ---- pills -----------------------------------------------------------------------------------------------------------

@Composable
fun Pill(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, icon: String? = null, light: Boolean = false, bg: Color = C.DarkPill) {
    val s = LocalScale.current
    Focusable(onClick, modifier) { focused ->
        val back = when { focused -> C.Plate; light -> C.Plate; else -> bg }
        val fore = if (focused || light) C.Rail else C.Plate
        Row(
            Modifier.height(s(72)).clip(RoundedCornerShape(s(36))).background(back).padding(horizontal = s(36)),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(s(12)),
        ) {
            if (icon != null) Icon(icon, 34, fore, filled = icon == Icons.Play)
            BasicText(label, style = text(26, FontWeight.Bold, color = fore))
        }
    }
}

/** A sentence that is also read out loud, with a small speaker in front so a grown-up knows it was spoken. */
@Composable
fun Spoken(line: String, modifier: Modifier = Modifier) {
    val s = LocalScale.current
    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(s(18))) {
        Icon(Icons.Speaker, 48)
        BasicText("“$line”", style = text(40, FontWeight.Medium))
    }
}

@Composable
fun Center(modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) =
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center, content = content)
