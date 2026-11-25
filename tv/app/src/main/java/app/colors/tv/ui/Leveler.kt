package app.colors.tv.ui

import android.media.audiofx.DynamicsProcessing
import android.util.Log
import androidx.annotation.OptIn
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import app.colors.tv.data.Audio
import kotlin.math.pow

/**
 * Evens out the volume (ADR 0041). The server measured how loud the video is and sends the gain that brings it to
 * the household's level; this turns it up or down with Android's DynamicsProcessing on the player's audio session,
 * softens loud moments with a gentle one-band compressor, and puts a limiter on top so nothing jumps out.
 *
 * If the TV can't give us the effect, a video that is too loud is still turned down with the player's own volume
 * (which can only go down, never up).
 */
@OptIn(UnstableApi::class)
class Leveler(private val player: ExoPlayer) {
    private var dp: DynamicsProcessing? = null
    private var want: Audio? = null

    private val listener = object : Player.Listener {
        override fun onAudioSessionIdChanged(audioSessionId: Int) {
            want?.let { attach(it) }
        }
    }

    init {
        player.addListener(listener)
    }

    fun apply(audio: Audio?) {
        want = audio
        if (audio == null) {
            release()
            player.volume = 1f
            return
        }
        attach(audio)
    }

    private fun attach(audio: Audio) {
        release()
        val session = player.audioSessionId
        val effect = try {
            if (session == 0) error("no audio session yet")
            DynamicsProcessing(0, session, config(audio.compress)).apply {
                setInputGainAllChannelsTo(audio.gainDb)
                if (audio.compress) setMbcBandAllChannelsTo(0, COMPRESSOR)
                setLimiterAllChannelsTo(LIMITER)
                enabled = true
            }
        } catch (e: Throwable) {  // no effect on this TV: at least never too loud
            Log.w(TAG, "volume levelling unavailable: ${e.message}")
            null
        }
        dp = effect
        player.volume = if (effect != null || audio.gainDb >= 0f) 1f else 10f.pow(audio.gainDb / 20f)
        if (effect != null) Log.i(TAG, "levelling session $session: ${audio.gainDb} dB, compress=${audio.compress}")
    }

    private fun release() {
        dp?.let { runCatching { it.enabled = false; it.release() } }
        dp = null
    }

    fun close() {
        player.removeListener(listener)
        release()
    }

    private companion object {
        const val TAG = "colors.level"

        fun config(compress: Boolean) = DynamicsProcessing.Config.Builder(
            DynamicsProcessing.VARIANT_FAVOR_FREQUENCY_RESOLUTION, 2,
            false, 0,               // no EQ before
            compress, 1,            // one compressor band over the whole range
            false, 0,               // no EQ after
            true,                   // the limiter
        ).build()

        // Above -20 dBFS, 2.5:1 with a soft knee: screams and sudden music come down a few dB, talking is left alone.
        // +2 dB after it gives back about what the compression takes from the overall level.
        val COMPRESSOR = DynamicsProcessing.MbcBand(
            true, 20000f, 10f, 200f, 2.5f, -20f, 8f, -90f, 1f, 0f, 2f,
        )

        // A ceiling at -1 dBFS: a quiet video turned up can't clip, and nothing ever jumps out.
        val LIMITER = DynamicsProcessing.Limiter(true, true, 0, 1f, 60f, 10f, -1f, 0f)
    }
}
