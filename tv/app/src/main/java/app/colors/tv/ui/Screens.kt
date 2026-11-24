package app.colors.tv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import app.colors.tv.R
import app.colors.tv.data.Api
import app.colors.tv.data.Card
import app.colors.tv.data.Container
import app.colors.tv.data.Home
import app.colors.tv.data.Profile
import app.colors.tv.data.TimeState
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Everything a screen needs from the app around it. */
class Nav(
    val api: Api,
    val go: (Screen) -> Unit,
    val replace: (Screen) -> Unit,
    /** Start over from this screen, with nothing behind it (choosing another profile). */
    val reset: (Screen) -> Unit,
    val back: () -> Unit,
    /** Play a recorded line: R.raw.voice_* (ADR 0040). */
    val say: (Int) -> Unit,
    val toast: (String) -> Unit,
)

sealed interface Screen {
    data object Start : Screen
    data class Server(val problem: String) : Screen
    data object Pairing : Screen
    data object Profiles : Screen
    data class Home(val profile: Profile) : Screen
    data class Channel(val profile: Profile, val containerId: Int) : Screen
    /** The menu's pages besides Home (Menu.kt). */
    data class Channels(val profile: Profile) : Screen
    data class Shelf(val profile: Profile, val kind: String) : Screen
    data class Player(val profile: Profile, val itemId: Int, val chain: Int = 0) : Screen
    data class Stopped(val profile: Profile, val time: TimeState?, val note: String = "") : Screen
}

/** Ask the server for playback; a refusal because time is up goes to the time-up screen (ADR 0017). */
fun startPlaying(nav: Nav, profile: Profile, card: Card) = nav.go(Screen.Player(profile, card.id))

// ---- first start: finding the server and pairing (ADR 0018, ADR 0039) ------------------------------------------------

@Composable
fun StartScreen(nav: Nav) {
    // The welcome plays once per launch while the server is asked; whichever takes longer decides when we move on.
    val welcome = remember { !Welcome.played }
    val welcomed = remember { CompletableDeferred<Unit>().also { if (!welcome) it.complete(Unit) } }
    LaunchedEffect(Unit) {
        val api = nav.api
        val reached = api.ping()
        val paired = if (!reached) null else try { if (api.token == null) null else api.pairStatus() } catch (e: Exception) { null }
        val profiles = if (paired != true) emptyList() else try { api.profiles() } catch (e: Exception) { emptyList() }
        welcomed.await()
        if (!reached) return@LaunchedEffect nav.replace(Screen.Server(
            if (api.server.isBlank()) "Type the address of your colors server." else "No answer from ${api.server}"))
        if (paired != true) return@LaunchedEffect nav.replace(Screen.Pairing)
        val last = profiles.firstOrNull { it.id == api.lastProfile }
        nav.replace(Screen.Profiles)
        if (last != null) nav.go(Screen.Home(last))
    }
    if (welcome) return WelcomeAnimation { Welcome.played = true; welcomed.complete(Unit) }
    Box(Modifier.fillMaxSize().background(C.Sky)) {
        Scenery()
        Center { Wordmark(120) }
    }
}

@Composable
fun ServerScreen(nav: Nav, problem: String) {
    val s = LocalScale.current
    var address by remember { mutableStateOf(nav.api.server) }
    val focus = remember { FocusRequester() }
    val scope = rememberCoroutineScope()
    val tryIt = {
        nav.api.server = address.trim()
        nav.replace(Screen.Start)
    }
    Box(Modifier.fillMaxSize()) {
        Scenery(dim = true)
        Column(Modifier.fillMaxWidth().offset(y = s(150)), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(36))) {
            Wordmark(96)
            BasicText("Can't find the colors server", style = text(56, playful = true))
            BasicText(problem, style = text(26, color = C.Faint))
            BasicTextField(
                address, { address = it },
                Modifier.width(s(900)).height(s(96)).clip(RoundedCornerShape(s(48))).background(C.Plate)
                    .padding(horizontal = s(40), vertical = s(24)).focusRequester(focus),
                textStyle = text(36, FontWeight.Medium, color = C.OnPlate),
                singleLine = true, cursorBrush = SolidColor(C.Rail),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Go),
                keyboardActions = KeyboardActions(onGo = { tryIt() }),
            )
            Pill("Try again", { scope.launch { tryIt() } })
            BasicText("The server's address, as it shows on the parents' page, for example http://192.168.1.10:8460", style = text(24, color = C.Faint))
        }
    }
    LaunchedEffect(Unit) { focus.soon() }
}

@Composable
fun PairingScreen(nav: Nav) {
    val s = LocalScale.current
    var code by remember { mutableStateOf<String?>(null) }
    var problem by remember { mutableStateOf("") }
    LaunchedEffect(Unit) {
        while (true) {
            // A fresh code every 14 minutes: a code works for 15 (ADR 0018).
            try { code = nav.api.pairStart(); problem = "" } catch (e: Exception) { problem = "The server didn't answer. Trying again…" }
            val until = System.currentTimeMillis() + 14 * 60_000
            while (System.currentTimeMillis() < until) {
                delay(3000)
                val paired = try { nav.api.pairStatus() } catch (e: Exception) { false }
                if (paired == true) {
                    nav.toast("This TV is paired")
                    return@LaunchedEffect nav.replace(Screen.Profiles)
                }
            }
        }
    }
    Box(Modifier.fillMaxSize()) {
        Scenery()
        Wordmark(96, Modifier.align(Alignment.TopCenter).offset(y = s(70)))
        Column(Modifier.fillMaxWidth().offset(y = s(232)), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(36))) {
            BasicText("Ask a grown-up", style = text(72, playful = true))
            Row(horizontalArrangement = Arrangement.spacedBy(s(20)), verticalAlignment = Alignment.CenterVertically) {
                (code ?: "······").forEachIndexed { i, d ->
                    if (i == 3) Spacer(Modifier.width(s(28)))
                    Box(Modifier.width(s(132)).height(s(168)).clip(RoundedCornerShape(s(28))).background(C.Plate), contentAlignment = Alignment.Center) {
                        BasicText(d.toString(), style = text(104, FontWeight.Bold, playful = true, color = C.Rail))
                    }
                }
            }
        }
        code?.let { QrCard("${nav.api.server}/admin/#tvs/$it", 300, "Scan with your phone", Modifier.align(Alignment.TopEnd).offset(x = -s(110), y = s(330))) }
        Column(Modifier.align(Alignment.TopCenter).offset(y = s(770)).width(s(1200)), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(14))) {
            BasicText(
                "Point your phone's camera at the square: it opens colors with this code filled in. Or open colors yourself and go to Kids › TVs › Pair a new TV.",
                style = text(34, FontWeight.Medium).copy(textAlign = TextAlign.Center),
            )
            BasicText(problem.ifEmpty { "Found the colors server at ${nav.api.server.substringAfter("//")} · The code works for 15 minutes" }, style = text(24, color = C.Faint))
        }
    }
}

// ---- who's watching ---------------------------------------------------------------------------------------------------

@Composable
fun ProfilesScreen(nav: Nav) {
    val s = LocalScale.current
    var profiles by remember { mutableStateOf<List<Profile>?>(null) }
    val first = remember { FocusRequester() }
    LaunchedEffect(Unit) {
        profiles = try { nav.api.profiles() } catch (e: Exception) {
            nav.replace(Screen.Server(e.message ?: "The server didn't answer")); null
        }
    }
    Box(Modifier.fillMaxSize()) {
        Scenery(dim = true)
        BasicText("Who's watching?", Modifier.align(Alignment.TopCenter).offset(y = s(165)), style = text(60, playful = true))
        val list = profiles ?: return@Box
        Row(Modifier.align(Alignment.TopCenter).offset(y = s(300)), horizontalArrangement = Arrangement.spacedBy(s(64))) {
            list.forEachIndexed { i, p ->
                val start = if (p.id == nav.api.lastProfile || (i == 0 && list.none { it.id == nav.api.lastProfile })) Modifier.focusRequester(first) else Modifier
                Focusable({ nav.api.lastProfile = p.id; nav.go(Screen.Home(p)) }, start.width(s(320))) { focused ->
                    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(24))) {
                        Box(Modifier.size(s(336)).border(s(12), if (focused) C.Plate else Color.Transparent, CircleShape), contentAlignment = Alignment.Center) {
                            Avatar(p, 288)
                        }
                        BasicText(p.name, style = text(36, color = if (focused) Color.White else Color(0xFFC9C9CF)))
                    }
                }
            }
        }
        if (list.isEmpty()) {
            BasicText("No profiles yet. Add the boys on the parents' page: Kids › Profiles.", Modifier.align(Alignment.Center), style = text(34))
        }
        LaunchedEffect(list) { if (list.isNotEmpty()) first.soon() }
    }
}

// ---- home (reference.md, Home) ---------------------------------------------------------------------------------------

private const val ROW_PITCH = 630

@Composable
fun HomeScreen(nav: Nav, profile: Profile) {
    val s = LocalScale.current
    var home by remember { mutableStateOf<Home?>(null) }
    var focusedRow by remember { mutableIntStateOf(0) }
    var focusedCol by remember { mutableIntStateOf(0) }
    val list = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val first = remember { FocusRequester() }
    val peekPx = with(LocalDensity.current) { s(432).roundToPx() }

    // Fresh rows on arrival and every minute, so a video that no longer fits drops out (ADR 0012).
    LaunchedEffect(profile.id) {
        while (true) {
            try {
                val h = nav.api.home(profile.id)
                if (!h.time.open) return@LaunchedEffect nav.replace(Screen.Stopped(profile, h.time))
                home = h
            } catch (e: Exception) {
                if (home == null) return@LaunchedEffect nav.replace(Screen.Server(e.message ?: "The server didn't answer"))
            }
            delay(60_000)
        }
    }
    val h = home
    MenuFrame(nav, h?.profile ?: profile, Menu.Home, menuWanted = focusedCol == 0, time = h?.time) {
        run {
            if (h == null) return@run
            if (h.lastPick) return@run OneMore(nav, profile, h)
            if (h.rows.isEmpty()) return@run Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                BasicText("Nothing to watch yet. Ask a grown-up to add some videos.", style = text(40, playful = true))
            }
            LazyColumn(
                state = list, modifier = Modifier.fillMaxSize(), userScrollEnabled = false,
                contentPadding = PaddingValues(top = s(126), bottom = s(1080 - 126 - ROW_PITCH)),
            ) {
                itemsIndexed(h.rows, key = { _, r -> r.id }) { ri, row ->
                    Column(Modifier.height(s(ROW_PITCH))) {
                        BasicText(row.title.uppercase(), Modifier.padding(start = s(84)).height(s(57)),
                            style = text(34, FontWeight.Bold, color = if (ri == focusedRow) C.Plate else C.Muted))
                        val rowState = rememberLazyListState()
                        LazyRow(state = rowState, contentPadding = PaddingValues(start = s(72), end = s(400)), horizontalArrangement = Arrangement.spacedBy(s(48))) {
                            itemsIndexed(row.cards, key = { _, c -> c.id }) { ci, card ->
                                VideoCard(
                                    card, onClick = { startPlaying(nav, profile, card) },
                                    modifier = if (ri == 0 && ci == 0) Modifier.focusRequester(first) else Modifier,
                                    onFocus = {
                                        focusedRow = ri; focusedCol = ci
                                        scope.launch { list.animateScrollToItem(ri) }
                                        scope.launch {
                                            // The focused card sits second, the one before it cut off on the left.
                                            if (ci >= 2) rowState.animateScrollToItem(ci - 2, peekPx) else rowState.animateScrollToItem(0)
                                        }
                                    },
                                )
                            }
                            if (row.containerId != null && row.cards.size >= 30) item {
                                Pill("More", { nav.go(Screen.Channel(profile, row.containerId)) }, Modifier.padding(top = s(110)))
                            }
                        }
                    }
                }
            }
            LaunchedEffect(h.rows.size) { first.soon() }
        }
    }
}

/** Three or fewer videos still fit: "one more" with up to three, said out loud (ADR 0012). */
@Composable
private fun OneMore(nav: Nav, profile: Profile, h: Home) {
    val s = LocalScale.current
    val picks = h.rows.flatMap { it.cards }.distinctBy { it.id }.take(3)
    val first = remember { FocusRequester() }
    LaunchedEffect(Unit) { nav.say(R.raw.voice_one_more) }
    Box(Modifier.fillMaxSize()) {
        Row(Modifier.offset(x = s(72), y = s(58)), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(s(24))) {
            Box(Modifier.size(s(104)).clip(CircleShape).background(C.Sun), contentAlignment = Alignment.Center) {
                BasicText("1", style = text(76, FontWeight.Bold, playful = true, color = C.Rail))
            }
            BasicText("One more!", style = text(72, playful = true))
        }
        Row(Modifier.offset(x = s(6), y = s(213)), horizontalArrangement = Arrangement.spacedBy(s(48))) {
            picks.forEachIndexed { i, c ->
                VideoCard(c, { startPlaying(nav, profile, c) }, if (i == 0) Modifier.focusRequester(first) else Modifier)
            }
        }
        Spoken("Pick one more. Then we're all done for today.", Modifier.align(Alignment.TopCenter).offset(y = s(820)))
    }
    LaunchedEffect(picks) { first.soon() }
}

// ---- a channel or show (reference.md, Channel page, scrolled) --------------------------------------------------------

@Composable
fun ChannelScreen(nav: Nav, profile: Profile, containerId: Int) {
    val s = LocalScale.current
    var page by remember { mutableStateOf<Container?>(null) }
    val first = remember { FocusRequester() }
    LaunchedEffect(containerId) {
        page = try { nav.api.container(containerId, profile.id) } catch (e: Exception) { nav.back(); null }
    }
    val p = page
    Box(Modifier.fillMaxSize().background(C.ChannelBg)) {
        if (p == null) return@Box
        BasicText(p.title, Modifier.offset(x = s(96), y = s(72)), style = text(56, playful = true))
        LazyVerticalGrid(
            GridCells.Fixed(3), Modifier.fillMaxSize().padding(top = s(204)),
            contentPadding = PaddingValues(start = s(84), end = s(84), bottom = s(200)),
            horizontalArrangement = Arrangement.spacedBy(s(12)), verticalArrangement = Arrangement.spacedBy(s(108)),
        ) {
            itemsIndexed(p.cards, key = { _, c -> c.id }) { i, c ->
                VideoCard(c, { startPlaying(nav, profile, c) }, if (i == 0) Modifier.focusRequester(first) else Modifier)
            }
        }
        LaunchedEffect(p.cards.size) { first.soon() }
    }
}

// ---- time's up, closed hours, stopped by a parent (ADR 0011, ADR 0039) ----------------------------------------------

@Composable
fun StoppedScreen(nav: Nav, profile: Profile, time: TimeState?, note: String) {
    val s = LocalScale.current
    val closed = time?.closedHours == true
    // The words on screen are the recorded line's words (tv/voice/lines.json), so they match what is heard.
    val (headline, line, clip) = when {
        closed -> Triple("Good night!", "The videos are sleeping. They wake up in the morning. Good night!", R.raw.voice_good_night)
        time?.reason == "Break time" -> Triple("Break time!", "Time for a little break. See you soon!", R.raw.voice_break)
        time?.reason == "Stopped by a parent" || note.isNotEmpty() ->
            Triple("All done for now!", "A grown-up says that's all for now. See you soon!", R.raw.voice_stopped)
        else -> Triple("All done for today!", "Great watching! All done for today. See you tomorrow!", R.raw.voice_all_done)
    }
    val first = remember { FocusRequester() }
    LaunchedEffect(Unit) {
        nav.say(clip)
        // A parent may add time from the phone: come back by itself when the app opens again.
        while (true) {
            delay(20_000)
            val h = try { nav.api.home(profile.id) } catch (e: Exception) { null }
            if (h != null && h.time.open) return@LaunchedEffect nav.replace(Screen.Home(profile))
        }
    }
    Box(Modifier.fillMaxSize()) {
        Scenery(dim = true)
        Column(Modifier.fillMaxWidth().offset(y = s(130)), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(30))) {
            Avatar(profile, 300)
            BasicText(headline, style = text(104, playful = true))
            Spoken(line)
        }
        Column(Modifier.align(Alignment.TopCenter).offset(y = s(836)), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(22))) {
            Pill("Who's watching?", { nav.replace(Screen.Profiles) }, Modifier.focusRequester(first))
            val hint = when {
                closed && time?.opensAt?.isNotEmpty() == true -> "Opens again at ${time.opensAt}."
                else -> "More time? Scan the square, or on your phone: colors › Kids › ${profile.name} › +10 min"
            }
            BasicText(hint, style = text(26, color = Color(0xFFB9B7D6)))
        }
        QrCard("${nav.api.server}/admin/#kid/${profile.id}", 220, "For grown-ups", Modifier.align(Alignment.TopEnd).offset(x = -s(96), y = s(742)))
    }
    LaunchedEffect(Unit) { first.soon() }
}
