package app.colors.tv.ui

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import app.colors.tv.data.ChannelTile
import app.colors.tv.data.Container
import app.colors.tv.data.Profile
import app.colors.tv.data.TimeState
import coil3.compose.AsyncImage
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.input.ImeAction
import app.colors.tv.data.Card
import kotlinx.coroutines.delay

/** The pages in the side menu. Home is the rows; the rest are whole lists (server: /channels, /shelf/<kind>). */
enum class Menu(val label: String, val icon: String, val kind: String?) {
    Home("Home", Icons.Home, null),
    Search("Search", Icons.Search, null),
    Channels("Channels", Icons.Channels, null),
    Recent("Recently watched", Icons.Recent, "recent"),
    Picked("Recommended", Icons.Star, "picked"),
    New("New", Icons.New, "new"),
}

/** The menu's width in design pixels. */
const val RAIL = 176

/** Go to another menu page. Home always sits right behind a menu page, so Home is a step back. */
fun openMenu(nav: Nav, profile: Profile, from: Menu, to: Menu) {
    if (to == from) return
    val target = when (to) {
        Menu.Home -> return nav.back()
        Menu.Channels -> Screen.Channels(profile)
        Menu.Search -> Screen.Search(profile)
        else -> Screen.Shelf(profile, to.kind!!)
    }
    if (from == Menu.Home) nav.go(target) else nav.replace(target)
}

/**
 * A menu page: the scenery, the side menu, and the page. The menu slides away while the remote is further right
 * than the first column (`menuWanted` false) and comes back when it is on the first column or in the menu.
 *
 * Both move with graphicsLayer, so nothing is laid out again while they slide: animating the menu's width made
 * every row lay itself out on every frame, which jittered on the Chromecast.
 */
@Composable
fun MenuFrame(
    nav: Nav, profile: Profile, current: Menu, menuWanted: Boolean, time: TimeState?,
    content: @Composable BoxScope.() -> Unit,
) {
    val s = LocalScale.current
    var inMenu by remember { mutableStateOf(false) }
    val hidden by animateFloatAsState(
        if (menuWanted || inMenu) 0f else 1f, tween(240, easing = FastOutSlowInEasing), label = "menu",
    )
    val railPx = with(LocalDensity.current) { s(RAIL).toPx() }
    Box(Modifier.fillMaxSize()) {
        Scenery()
        Box(Modifier.fillMaxSize().graphicsLayer { translationX = railPx * (1f - hidden) }, content = content)
        SideRail(nav, profile, current, Modifier.graphicsLayer { translationX = -railPx * hidden }.onFocusChanged { inMenu = it.hasFocus })
        Wordmark(60, Modifier.align(Alignment.TopEnd).offset(x = -s(104), y = s(66)))
        if (time != null) TimerPill(time, Modifier.align(Alignment.TopEnd).offset(x = -s(372), y = s(70)))
    }
}

/** The profile (bigger, with a thick ring when it has the focus), the five pages, and the grown-ups' QR code. */
@Composable
fun SideRail(nav: Nav, profile: Profile, current: Menu, modifier: Modifier = Modifier) {
    val s = LocalScale.current
    Column(
        modifier.width(s(RAIL)).fillMaxHeight().background(C.Rail).padding(top = s(34)),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Focusable({ nav.reset(Screen.Profiles) }) { focused ->
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(8))) {
                Box(
                    Modifier.size(s(136)).border(s(8), if (focused) C.Plate else Color.Transparent, CircleShape).padding(s(14)),
                    contentAlignment = Alignment.Center,
                ) { Avatar(profile, 108) }
                BasicText(profile.name, style = text(24, if (focused) FontWeight.Bold else FontWeight.Medium, color = if (focused) Color.White else C.Plate))
            }
        }
        Spacer(Modifier.height(s(22)))
        Menu.entries.forEach { m ->
            val here = m == current
            Focusable({ openMenu(nav, profile, current, m) }, Modifier.width(s(RAIL)).height(s(100))) { focused ->
                Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(4))) {
                    Box(
                        Modifier.size(s(60)).clip(CircleShape).background(
                            when { focused -> C.Plate; here -> Color.White.copy(alpha = .16f); else -> Color.Transparent },
                        ),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(m.icon, 34, if (focused) C.Rail else if (here) Color.White else C.Plate.copy(alpha = .78f), filled = m == Menu.Home)
                    }
                    BasicText(
                        m.label, Modifier.padding(horizontal = s(8)),
                        style = text(19, if (focused || here) FontWeight.Bold else FontWeight.Medium, color = if (focused || here) Color.White else C.Plate.copy(alpha = .78f))
                            .copy(textAlign = TextAlign.Center, lineHeight = s.sp(22)),
                        maxLines = 2,
                    )
                }
            }
        }
        Spacer(Modifier.weight(1f))
        // Opens this child's page in the parents' app: add time, last one, end now (ADR 0039).
        QrCard("${nav.api.server}/admin/#kid/${profile.id}", 116, "Grown-ups", labelPx = 18, small = true)
        Spacer(Modifier.height(s(30)))
    }
}

// ---- Channels -----------------------------------------------------------------------------------------------------

@Composable
fun ChannelsScreen(nav: Nav, profile: Profile) {
    val s = LocalScale.current
    var tiles by remember { mutableStateOf<List<ChannelTile>?>(null) }
    val first = remember { FocusRequester() }
    LaunchedEffect(profile.id) { tiles = try { nav.api.channels(profile.id) } catch (e: Exception) { emptyList() } }
    // Five circles fit beside the menu, so the menu stays.
    MenuFrame(nav, profile, Menu.Channels, menuWanted = true, time = null) {
        val t = tiles ?: return@MenuFrame
        BasicText("Channels", Modifier.offset(x = s(84), y = s(64)), style = text(56, playful = true))
        if (t.isEmpty()) return@MenuFrame Empty("No channels to watch right now.")
        LazyVerticalGrid(
            GridCells.Fixed(5), Modifier.fillMaxSize().padding(top = s(190)),
            contentPadding = PaddingValues(start = s(56), end = s(232), bottom = s(120)),
            verticalArrangement = Arrangement.spacedBy(s(36)),
        ) {
            itemsIndexed(t, key = { _, c -> c.id }) { i, c ->
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.TopCenter) {
                    Focusable({ nav.go(Screen.Channel(profile, c.id)) }, if (i == 0) Modifier.focusRequester(first) else Modifier) { focused ->
                        Column(Modifier.width(s(290)), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(s(14))) {
                            Box(
                                Modifier.size(s(232)).border(s(8), if (focused) C.Plate else Color.Transparent, CircleShape)
                                    .padding(s(14)).clip(CircleShape).background(Color(0xFF2A2A2A)),
                            ) { AsyncImage(c.picture, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
                            BasicText(
                                c.title, style = text(28, FontWeight.Bold, color = if (focused) Color.White else C.Plate).copy(textAlign = TextAlign.Center),
                                maxLines = 2, overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                }
            }
        }
        LaunchedEffect(t.size) { first.soon() }
    }
}

// ---- Recently watched, Recommended, New ---------------------------------------------------------------------------

@Composable
fun ShelfScreen(nav: Nav, profile: Profile, kind: String) {
    val s = LocalScale.current
    val menu = Menu.entries.first { it.kind == kind }
    var page by remember { mutableStateOf<Container?>(null) }
    var col by remember { mutableIntStateOf(0) }
    val first = remember { FocusRequester() }
    LaunchedEffect(kind) { page = try { nav.api.shelf(kind, profile.id) } catch (e: Exception) { Container(0, menu.label, emptyList()) } }
    MenuFrame(nav, profile, menu, menuWanted = col == 0, time = null) {
        val p = page ?: return@MenuFrame
        BasicText(menu.label, Modifier.offset(x = s(84), y = s(64)), style = text(56, playful = true))
        if (p.cards.isEmpty()) return@MenuFrame Empty(
            when (kind) { "recent" -> "Nothing watched yet."; "picked" -> "Nothing to recommend yet."; else -> "Nothing new right now." },
        )
        LazyVerticalGrid(
            GridCells.Fixed(3), Modifier.fillMaxSize().padding(top = s(190)),
            contentPadding = PaddingValues(start = s(72), end = s(72), bottom = s(200)),
            horizontalArrangement = Arrangement.spacedBy(s(12)), verticalArrangement = Arrangement.spacedBy(s(40)),
        ) {
            itemsIndexed(p.cards, key = { _, c -> c.id }) { i, c ->
                VideoCard(c, { startPlaying(nav, profile, c) }, if (i == 0) Modifier.focusRequester(first) else Modifier, onFocus = { col = i % 3 })
            }
        }
        LaunchedEffect(p.cards.size) { first.soon() }
    }
}

// ---- Search: this child's own library only ------------------------------------------------------------------------

@Composable
fun SearchScreen(nav: Nav, profile: Profile) {
    val s = LocalScale.current
    var field by remember { mutableStateOf(TextFieldValue("")) }
    val query = field.text
    var results by remember { mutableStateOf<List<Card>?>(null) }
    var col by remember { mutableIntStateOf(0) }
    val box = remember { FocusRequester() }
    val firstResult = remember { FocusRequester() }
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    // Ask once typing (or speaking) pauses, not on every letter.
    LaunchedEffect(query) {
        if (query.isBlank()) { results = null; return@LaunchedEffect }
        delay(350)
        results = try { nav.api.search(query, profile.id) } catch (e: Exception) { emptyList() }
    }
    MenuFrame(nav, profile, Menu.Search, menuWanted = col == 0, time = null) {
        Row(
            Modifier.offset(x = s(84), y = s(66)).width(s(1120)).height(s(96)).clip(RoundedCornerShape(s(48)))
                .background(C.Plate).padding(horizontal = s(36)),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(s(20)),
        ) {
            Icon(Icons.Search, 44, C.Rail)
            Box(Modifier.weight(1f), contentAlignment = Alignment.CenterStart) {
                if (query.isEmpty()) BasicText("Search your videos", style = text(36, FontWeight.Medium, color = C.Muted))
                BasicTextField(
                    field, { field = if (it.text.length <= 60) it else field },
                    Modifier.fillMaxWidth().focusRequester(box).onFocusChanged { if (it.isFocused) col = 0 }
                        // The box keeps the arrows for its cursor; Down still goes to the results and Left, from the
                        // start of the text, to the menu.
                        .onPreviewKeyEvent { e ->
                            if (e.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                            when {
                                e.key == Key.DirectionDown -> {
                                    keyboard?.hide()
                                    if (results.isNullOrEmpty()) false else runCatching { firstResult.requestFocus() }.isSuccess
                                }
                                e.key == Key.DirectionLeft && field.selection.start == 0 -> focus.moveFocus(FocusDirection.Left)
                                else -> false
                            }
                        },
                    textStyle = text(36, FontWeight.Medium, color = C.OnPlate), singleLine = true,
                    cursorBrush = SolidColor(C.Rail),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { keyboard?.hide(); runCatching { firstResult.requestFocus() } }),
                )
            }
        }
        val r = results
        when {
            r == null -> Empty("Type, or press the mic on the remote and say it.")
            r.isEmpty() -> Empty("Nothing found for “$query”.")
            else -> LazyVerticalGrid(
                GridCells.Fixed(3), Modifier.fillMaxSize().padding(top = s(210)),
                contentPadding = PaddingValues(start = s(72), end = s(72), bottom = s(200)),
                horizontalArrangement = Arrangement.spacedBy(s(12)), verticalArrangement = Arrangement.spacedBy(s(40)),
            ) {
                itemsIndexed(r, key = { _, c -> c.id }) { i, c ->
                    VideoCard(c, { startPlaying(nav, profile, c) }, if (i == 0) Modifier.focusRequester(firstResult) else Modifier,
                        onFocus = { col = i % 3 })
                }
            }
        }
    }
    LaunchedEffect(Unit) { box.soon() }
}

@Composable
private fun BoxScope.Empty(line: String) {
    BasicText(line, Modifier.align(Alignment.Center), style = text(40, playful = true))
}
