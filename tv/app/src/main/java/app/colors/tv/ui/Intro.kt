package app.colors.tv.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Whether the welcome has played since the app started: once per launch, like YouTube's. */
object Welcome {
    var played = false
}

/**
 * The welcome, about 1.9 s: the six letters of "colors" spring up one after another, each in its own colour, a
 * rainbow line draws under them, and the letters hop once in a wave. `onDone` is called at the end; the last frame
 * stays until the app moves on.
 */
@Composable
fun WelcomeAnimation(onDone: () -> Unit) {
    val s = LocalScale.current
    val word = "colors"
    val pops = remember { List(word.length) { Animatable(0f) } }
    val hops = remember { List(word.length) { Animatable(0f) } }
    val line = remember { Animatable(0f) }
    val density = LocalDensity.current
    val rise = with(density) { s(150).toPx() }
    val hopPx = with(density) { s(44).toPx() }

    LaunchedEffect(Unit) {
        pops.forEachIndexed { i, a ->
            launch { delay(120L + i * 105L); a.animateTo(1f, spring(dampingRatio = 0.42f, stiffness = Spring.StiffnessLow)) }
        }
        launch { delay(900); line.animateTo(1f, tween(420, easing = FastOutSlowInEasing)) }
        hops.forEachIndexed { i, a ->
            launch {
                delay(1180L + i * 65L)
                a.animateTo(1f, tween(150, easing = FastOutSlowInEasing))
                a.animateTo(0f, spring(dampingRatio = 0.5f, stiffness = Spring.StiffnessMediumLow))
            }
        }
        delay(1900)
        onDone()
    }

    Box(Modifier.fillMaxSize().background(C.Sky), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(6))) {
            Row(verticalAlignment = Alignment.Bottom) {
                word.forEachIndexed { i, ch ->
                    BasicText(
                        ch.toString(),
                        Modifier.graphicsLayer {
                            val p = pops[i].value
                            alpha = p.coerceIn(0f, 1f)
                            scaleX = p; scaleY = p
                            rotationZ = (1f - p) * -28f
                            translationY = (1f - p) * rise - hops[i].value * hopPx
                            transformOrigin = TransformOrigin(0.5f, 1f)
                        },
                        style = text(230, FontWeight.Bold, playful = true, color = C.Letters[i]),
                    )
                }
            }
            Canvas(Modifier.width(s(600)).height(s(20))) {
                val w = size.width * line.value
                if (w > 0f) drawRoundRect(
                    Brush.horizontalGradient(C.Letters, endX = size.width), size = Size(w, size.height),
                    cornerRadius = CornerRadius(size.height / 2),
                )
            }
        }
    }
}
