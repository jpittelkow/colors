package app.colors.tv.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.colors.tv.R

/**
 * The look, measured from a kids profile in the YouTube TV app (docs/design/reference.md, ADR 0016).
 * Every size in this app is written in pixels of a 1920x1080 screen and scaled to the TV's real size,
 * so a TV that runs its interface at 720p or 1080p shows the same layout.
 */
object C {
    val Rail = Color(0xFF1A0059)
    val Sky = Color(0xFF0F0F0F)
    val Hills = Color(0xFF7F00BF)
    val Ground = Color(0xFF2C2580)
    val Cloud = Color(0xFF42414A)
    val Plate = Color(0xFFF1F1F1)
    val OnPlate = Color(0xFF0F0F0F)
    val Muted = Color(0xFF9F9EA6)
    val Red = Color(0xFFFF0033)
    val DimSky = Color(0xFF050505)
    val DimGround = Color(0xFF00001F)
    val DarkPill = Color(0xFF1A1A36)
    val PlayerPill = Color(0xFF2B2B27)
    val ChannelBg = Color(0xFF362B7A)
    val Sun = Color(0xFFFFC233)
    val Orange = Color(0xFFFF7A45)
    val Faint = Color(0xFFC9C7E6)

    /** The name, one colour per letter (ADR 0038). */
    val Letters = listOf(0xFFFF5A5F, 0xFFFF9F1C, 0xFFFFD23F, 0xFF5CD65C, 0xFF4DA3FF, 0xFFB57BFF).map { Color(it) }

    /** Avatar circle colours, the same names as the parents' page (ADR 0036). */
    fun avatar(name: String): Color = when (name) {
        "sky" -> Color(0xFFA9CDF5); "sun" -> Color(0xFFFFD96B); "coral" -> Color(0xFFF4A983)
        "mint" -> Color(0xFF9FDFC4); "grape" -> Color(0xFFBDB5F5); "leaf" -> Color(0xFFB4E09C)
        "berry" -> Color(0xFFF5A9C9); "sand" -> Color(0xFFE8D3A8); else -> Color(0xFF6C67A6)
    }
}

val Fredoka = FontFamily(
    Font(R.font.fredoka_semibold, FontWeight.SemiBold),
    Font(R.font.fredoka_bold, FontWeight.Bold),
)

/** One design pixel (of 1920) in this TV's dp, and the matching text size. */
class Scale(val px: Float, private val fontScale: Float) {
    operator fun invoke(v: Number): Dp = (v.toFloat() * px).dp
    fun sp(v: Number): TextUnit = (v.toFloat() * px / fontScale).sp
}

val LocalScale = compositionLocalOf { Scale(0.5f, 1f) }

@Composable
fun ProvideScale(content: @Composable () -> Unit) {
    val cfg = LocalConfiguration.current
    val density = LocalDensity.current
    val s = Scale(cfg.screenWidthDp / 1920f, density.fontScale)
    CompositionLocalProvider(LocalScale provides s, content = content)
}

@Composable
fun text(px: Number, weight: FontWeight = FontWeight.Normal, playful: Boolean = false, color: Color = C.Plate): TextStyle {
    val s = LocalScale.current
    return TextStyle(
        color = color,
        fontSize = s.sp(px),
        lineHeight = s.sp(px.toFloat() * 1.32f),
        fontWeight = if (playful && weight == FontWeight.Normal) FontWeight.SemiBold else weight,
        fontFamily = if (playful) Fredoka else FontFamily.Default,
    )
}

val Zero = 0.dp
