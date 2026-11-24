package app.colors.tv

import android.os.Bundle
import android.media.MediaPlayer
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import app.colors.tv.data.Api
import app.colors.tv.ui.C
import app.colors.tv.ui.ChannelScreen
import app.colors.tv.ui.ChannelsScreen
import app.colors.tv.ui.ShelfScreen
import app.colors.tv.ui.HomeScreen
import app.colors.tv.ui.Nav
import app.colors.tv.ui.PairingScreen
import app.colors.tv.ui.PlayerScreen
import app.colors.tv.ui.ProfilesScreen
import app.colors.tv.ui.ProvideScale
import app.colors.tv.ui.Screen
import app.colors.tv.ui.ServerScreen
import app.colors.tv.ui.StartScreen
import app.colors.tv.ui.StoppedScreen
import coil3.ImageLoader
import coil3.SingletonImageLoader
import coil3.network.okhttp.OkHttpNetworkFetcherFactory
import coil3.svg.SvgDecoder

class MainActivity : ComponentActivity() {
    private lateinit var api: Api
    private var voice: MediaPlayer? = null

    /** Play one of the recorded lines (ADR 0040), stopping any line still playing. */
    private fun say(clip: Int) {
        voice?.release()
        voice = MediaPlayer.create(this, clip)?.apply {
            setOnCompletionListener { it.release(); if (voice === it) voice = null }
            start()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        api = Api(this)
        // Debug builds only: point the TV at another server with
        //   adb shell am start -n app.colors.tv/.MainActivity --es server http://host:8460
        // A release build ignores it, so another app on the TV can't send colors to a server of its choosing.
        // In a release the address is changed on the TV itself (the "Can't find the server" screen).
        if (BuildConfig.DEBUG) intent?.getStringExtra("server")?.let { api.server = it; api.token = null }

        // Pictures (thumbnails, profile pictures, SVG characters) load through the same client, so the TV's
        // token goes with requests to our own server only (Api.http).
        SingletonImageLoader.setSafe { ctx ->
            ImageLoader.Builder(ctx).components {
                add(OkHttpNetworkFetcherFactory(callFactory = { api.http }))
                add(SvgDecoder.Factory())
            }.build()
        }
        setContent {
            val stack = remember { mutableStateListOf<Screen>(Screen.Start) }
            val nav = remember {
                Nav(
                    api = api,
                    go = { stack.add(it) },
                    replace = { if (stack.isNotEmpty()) stack.removeAt(stack.lastIndex); stack.add(it) },
                    reset = { stack.clear(); stack.add(it) },
                    back = { if (stack.size > 1) stack.removeAt(stack.lastIndex) else finish() },
                    say = { clip -> say(clip) },
                    toast = { msg -> Toast.makeText(this, msg, Toast.LENGTH_LONG).show() },
                )
            }
            BackHandler(enabled = stack.size > 1) { stack.removeAt(stack.lastIndex) }
            ProvideScale {
                Box(Modifier.fillMaxSize().background(C.Sky)) {
                    val sc = stack.last()
                    // Each screen starts fresh, even when one player replaces another.
                    key(stack.size, sc) { when (sc) {
                        Screen.Start -> StartScreen(nav)
                        is Screen.Server -> ServerScreen(nav, sc.problem)
                        Screen.Pairing -> PairingScreen(nav)
                        Screen.Profiles -> ProfilesScreen(nav)
                        is Screen.Home -> HomeScreen(nav, sc.profile)
                        is Screen.Channel -> ChannelScreen(nav, sc.profile, sc.containerId)
                        is Screen.Channels -> ChannelsScreen(nav, sc.profile)
                        is Screen.Shelf -> ShelfScreen(nav, sc.profile, sc.kind)
                        is Screen.Player -> PlayerScreen(nav, sc.profile, sc.itemId, sc.chain)
                        is Screen.Stopped -> StoppedScreen(nav, sc.profile, sc.time, sc.note)
                    } }
                }
            }
        }
    }

    override fun onDestroy() {
        voice?.release()
        super.onDestroy()
    }
}
