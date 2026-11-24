import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

// Release signing: tv/keystore.properties (git-ignored) points at the key, which lives outside the repo. Without
// it a release build comes out unsigned. Keep the key: a TV can only take an update signed by the same key.
val releaseKey = Properties().apply {
    rootProject.file("keystore.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
}

// This household's own settings, in tv/local.properties (git-ignored, beside the SDK path):
//   colors.server = http://192.168.1.10:8460   the server a fresh TV tries first; blank asks on the TV
//   colors.res    = /path/to/res               resources that replace the built-in ones (an icon, a banner)
val local = Properties().apply {
    rootProject.file("local.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
}

android {
    namespace = "app.colors.tv"
    compileSdk = 37

    defaultConfig {
        applicationId = "app.colors.tv"
        // 30 = Android 11: the oldest TVs in the house are the office TCL and the SHIELD (ADR 0015).
        minSdk = 30
        targetSdk = 34
        versionCode = 5
        versionName = "0.3.2"
        // Where the server is, unless a parent typed another address on the TV (ADR 0018).
        buildConfigField("String", "DEFAULT_SERVER", "\"${local.getProperty("colors.server", "")}\"")
    }

    signingConfigs {
        if (releaseKey.isNotEmpty()) create("release") {
            storeFile = file(releaseKey.getProperty("storeFile"))
            storePassword = releaseKey.getProperty("storePassword")
            keyAlias = releaseKey.getProperty("keyAlias")
            keyPassword = releaseKey.getProperty("keyPassword")
        }
    }

    buildTypes {
        // A debug build installs beside the release one, so testing never unpairs a TV.
        debug {
            applicationIdSuffix = ".dev"
            resValue("string", "app_name", "colors dev")
        }
        release {
            resValue("string", "app_name", "colors")
            // R8 makes Compose noticeably faster on the Chromecast (fewer slow frames when rows scroll).
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            signingConfig = signingConfigs.findByName("release")
        }
        // The release build (R8 and all) pointed at the dev server through `adb reverse tcp:8455 tcp:8455`, beside
        // the real app: checks a release change without touching a child's history on the live server.
        create("staging") {
            initWith(getByName("release"))
            applicationIdSuffix = ".staging"
            resValue("string", "app_name", "colors staging")
            buildConfigField("String", "DEFAULT_SERVER", "\"http://127.0.0.1:8455\"")
            matchingFallbacks += "release"
        }
    }

    // A household's own icon and banner win over the built-in ones in every build type.
    local.getProperty("colors.res")?.let { dir ->
        listOf("debug", "release", "staging").forEach { sourceSets.getByName(it).res.srcDir(dir) }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
        resValues = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)

    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.foundation)
    implementation(libs.compose.ui.tooling.preview)

    implementation(libs.media3.exoplayer)
    implementation(libs.media3.ui)
    implementation(libs.media3.okhttp)
    implementation(libs.coil.compose)
    implementation(libs.coil.svg)
    implementation(libs.coil.okhttp)
    implementation(libs.okhttp)
    implementation(libs.zxing.core)
    implementation(libs.coroutines.android)

    testImplementation(libs.junit)
}
