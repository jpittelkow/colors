package app.colors.tv.data

import android.content.Context
import app.colors.tv.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/** The TV API (ADR 0017): the server sends finished screens; this app draws them and never filters them. */
class Api(context: Context) {
    private val prefs = context.getSharedPreferences("colors", Context.MODE_PRIVATE)

    /** Where the server is. A parent can change it on the TV; otherwise the address built into the app. */
    var server: String
        get() = prefs.getString("server", null) ?: BuildConfig.DEFAULT_SERVER
        set(v) = prefs.edit().putString("server", v.trimEnd('/')).apply()

    /** This TV's token (ADR 0018). Kept in the app's private storage; it is worthless once revoked in the page. */
    var token: String?
        get() = prefs.getString("token", null)
        set(v) = prefs.edit().apply { if (v == null) remove("token") else putString("token", v) }.apply()

    /** The profile last picked on this TV, so the app opens on it. */
    var lastProfile: Int
        get() = prefs.getInt("profile", 0)
        set(v) = prefs.edit().putInt("profile", v).apply()

    val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            val req = chain.request()
            val t = token
            // The token only ever goes to our own server, never to an outside address.
            if (t != null && req.url.toString().startsWith(server)) {
                chain.proceed(req.newBuilder().header("Authorization", "Bearer $t").build())
            } else chain.proceed(req)
        }
        .build()

    fun url(path: String): String = if (path.startsWith("http")) path else server + path

    private suspend fun call(method: String, path: String, body: JSONObject? = null): Any? = withContext(Dispatchers.IO) {
        val b = Request.Builder().url(url("$API$path"))
        if (method == "POST") b.post((body ?: JSONObject()).toString().toRequestBody(JSON)) else b.get()
        http.newCall(b.build()).execute().use { res ->
            val text = res.body.string()
            if (!res.isSuccessful) throw ApiError(res.code, text)
            if (text.isBlank()) null else if (text.trimStart().startsWith("[")) JSONArray(text) else JSONObject(text)
        }
    }

    // ---- pairing ----------------------------------------------------------------------------------------------------

    suspend fun ping(): Boolean = withContext(Dispatchers.IO) {
        try {
            http.newCall(Request.Builder().url(url("/healthz")).build()).execute().use { it.isSuccessful }
        } catch (e: Exception) {  // IOException, or a blank or malformed address
            false
        }
    }

    /** Ask for a code to show. The token works once a parent types the code in the page. */
    suspend fun pairStart(): String {
        val o = call("POST", "/pair/start") as JSONObject
        token = o.getString("token")
        return o.getString("code")
    }

    /** null: the token is unknown or revoked (pair again); false: waiting for a parent; true: paired. */
    suspend fun pairStatus(): Boolean? = try {
        (call("GET", "/pair/status") as JSONObject).getBoolean("paired")
    } catch (e: ApiError) {
        if (e.code == 401) null else throw e
    }

    // ---- screens ----------------------------------------------------------------------------------------------------

    suspend fun profiles(): List<Profile> = (call("GET", "/profiles") as JSONArray).objects().map(::profile)

    suspend fun home(profileId: Int): Home {
        val o = call("GET", "/home?profile_id=$profileId") as JSONObject
        return Home(
            profile = profile(o.getJSONObject("profile")),
            time = time(o.getJSONObject("time")),
            lastPick = o.optBoolean("last_pick"),
            rows = o.getJSONArray("rows").objects().map { r ->
                Row(
                    id = r.getString("id"),
                    title = r.getString("title"),
                    containerId = if (r.has("container_id")) r.getInt("container_id") else null,
                    cards = r.getJSONArray("cards").objects().map(::card),
                )
            },
        )
    }

    suspend fun container(id: Int, profileId: Int): Container {
        val o = call("GET", "/container/$id?profile_id=$profileId") as JSONObject
        return Container(o.getInt("id"), o.getString("title"), o.getJSONArray("cards").objects().map(::card))
    }

    /** The menu's Channels page: every channel with something to watch now. */
    suspend fun channels(profileId: Int): List<ChannelTile> =
        (call("GET", "/channels?profile_id=$profileId") as JSONObject).getJSONArray("channels").objects().map {
            ChannelTile(it.getInt("id"), it.getString("title"), it.optInt("count"), it.optInt("unwatched"),
                url(it.getString("picture")), it.optBoolean("round"))
        }

    /** One of the menu's lists: "recent", "picked" or "new". */
    suspend fun shelf(kind: String, profileId: Int): Container {
        val o = call("GET", "/shelf/$kind?profile_id=$profileId") as JSONObject
        return Container(0, o.getString("title"), o.getJSONArray("cards").objects().map(::card))
    }

    /** Search this child's own library (titles and channels); never YouTube. */
    suspend fun search(query: String, profileId: Int): List<Card> {
        val q = java.net.URLEncoder.encode(query, "UTF-8")
        val o = call("GET", "/search?profile_id=$profileId&q=$q") as JSONObject
        return o.getJSONArray("cards").objects().map(::card)
    }

    /** A code that changes when this child's limits or today's parent actions change: reload when it does. */
    suspend fun stamp(profileId: Int): String =
        (call("GET", "/stamp?profile_id=$profileId") as JSONObject).getString("stamp")

    suspend fun upNext(profileId: Int, itemId: Int): Pair<Int, List<Card>> {
        val o = call("GET", "/upnext?profile_id=$profileId&item_id=$itemId") as JSONObject
        return o.optInt("autoplay_n", 2) to o.getJSONArray("cards").objects().map(::card)
    }

    // ---- playback ---------------------------------------------------------------------------------------------------

    /** The server checks every rule again (ADR 0017). A refusal comes back as [Refused] with a reason to show. */
    suspend fun play(profileId: Int, itemId: Int): Play {
        val o = try {
            call("POST", "/play", JSONObject().put("profile_id", profileId).put("item_id", itemId)) as JSONObject
        } catch (e: ApiError) {
            val d = e.detail()
            if (e.code == 403 && d != null) throw Refused(d.optString("reason"), d.optString("message"), d.optJSONObject("time")?.let(::time))
            throw e
        }
        return Play(
            card = card(o.getJSONObject("item")),
            streamUrl = url(o.getString("stream_url")),
            resumeS = o.optDouble("resume_s", 0.0),
            skip = o.getJSONArray("skip_segments").objects().map { Segment(it.getDouble("start_s"), it.getDouble("end_s")) },
            heartbeatS = o.optInt("heartbeat_s", 15),
            time = time(o.getJSONObject("time")),
        )
    }

    /** Counts watched time and saves the resume point. The answer may tell the app to stop (ADR 0011). */
    suspend fun heartbeat(profileId: Int, itemId: Int, positionS: Double, state: String): Beat {
        val o = call(
            "POST", "/heartbeat",
            JSONObject().put("profile_id", profileId).put("item_id", itemId).put("position_s", positionS).put("state", state),
        ) as JSONObject
        return Beat(o.optString("command").takeIf { it.isNotEmpty() && it != "null" }, o.optString("reason"), o.optJSONObject("time")?.let(::time))
    }

    // ---- parsing ----------------------------------------------------------------------------------------------------

    private fun profile(o: JSONObject) = Profile(
        id = o.getInt("id"), name = o.getString("name"), kind = o.optString("kind", "child"),
        avatarUrl = o.optString("avatar_url").takeIf { it.isNotEmpty() }?.let(::url),
        avatarColor = o.optString("avatar_color"),
    )

    private fun card(o: JSONObject) = Card(
        id = o.getInt("id"), title = o.getString("title"), containerId = o.getInt("container_id"),
        containerTitle = o.optString("container_title"), durationS = o.optDouble("duration_s", 0.0),
        remainingS = o.optDouble("remaining_s", 0.0), positionS = o.optDouble("position_s", 0.0),
        watched = o.optBoolean("watched"), thumb = url(o.getString("thumb")),
    )

    private fun time(o: JSONObject) = TimeState(
        open = o.optBoolean("open", true), reason = o.optString("reason"), limited = o.optBoolean("limited"),
        leftS = if (o.isNull("left_s")) null else o.getDouble("left_s"), showTimer = o.optBoolean("show_timer", true),
        lastOne = o.optBoolean("lastone"), opensAt = o.optString("opens_at"),
    )

    companion object {
        const val API = "/api/tv/v1"
        private val JSON = "application/json".toMediaType()
    }
}

class ApiError(val code: Int, val body: String) : IOException("Server said $code") {
    fun detail(): JSONObject? = try { JSONObject(body).optJSONObject("detail") } catch (e: Exception) { null }
}

class Refused(val reason: String, override val message: String, val time: TimeState?) : IOException(message)

private fun JSONArray.objects(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }

data class Profile(val id: Int, val name: String, val kind: String, val avatarUrl: String?, val avatarColor: String)

data class Card(
    val id: Int, val title: String, val containerId: Int, val containerTitle: String, val durationS: Double,
    val remainingS: Double, val positionS: Double, val watched: Boolean, val thumb: String,
)

data class Row(val id: String, val title: String, val containerId: Int?, val cards: List<Card>)

data class TimeState(
    val open: Boolean, val reason: String, val limited: Boolean, val leftS: Double?, val showTimer: Boolean,
    val lastOne: Boolean, val opensAt: String,
) {
    /** Closed hours (a clock time), as opposed to time used up. */
    val closedHours get() = !open && reason == "Closed now"
}

data class Home(val profile: Profile, val time: TimeState, val lastPick: Boolean, val rows: List<Row>)

data class Container(val id: Int, val title: String, val cards: List<Card>)

/** A channel on the Channels page. `round` = the channel's own picture; otherwise its newest video's. */
data class ChannelTile(val id: Int, val title: String, val count: Int, val unwatched: Int, val picture: String, val round: Boolean)

data class Segment(val startS: Double, val endS: Double)

data class Play(
    val card: Card, val streamUrl: String, val resumeS: Double, val skip: List<Segment>, val heartbeatS: Int,
    val time: TimeState,
)

data class Beat(val command: String?, val reason: String, val time: TimeState?)
