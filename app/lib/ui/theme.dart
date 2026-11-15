import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class Palette {
  static const blue = Color(0xFF2E6BFF);
  static const cyan = Color(0xFF00C2FF);
  static const up = Color(0xFFFF5C6C); // price went up (bad)
  static const down = Color(0xFF2BD99F); // price went down (good)
  static const amber = Color(0xFFFFB547);

  static const bg = Color(0xFF080C16);
  static const surface = Color(0xFF111827);
  static const surface2 = Color(0xFF182136);
  static const line = Color(0xFF243049);
  static const text = Color(0xFFEFF3FF);
  static const muted = Color(0xFF8A96B3);

  static const heroGradient = LinearGradient(
    colors: [Color(0xFF1A3DFF), Color(0xFF0090FF), Color(0xFF00C2FF)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: Palette.blue,
    brightness: Brightness.dark,
    surface: Palette.surface,
    primary: Palette.blue,
    secondary: Palette.cyan,
  );
  final base = ThemeData(useMaterial3: true, colorScheme: scheme, brightness: Brightness.dark);
  return base.copyWith(
    scaffoldBackgroundColor: Palette.bg,
    textTheme: base.textTheme.apply(bodyColor: Palette.text, displayColor: Palette.text),
    cardTheme: CardThemeData(
      color: Palette.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: Palette.line, width: 1),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Palette.surface,
      indicatorColor: Palette.blue.withValues(alpha: .22),
      labelTextStyle: WidgetStateProperty.all(const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
      height: 68,
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: Palette.surface2,
      side: const BorderSide(color: Palette.line),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      labelStyle: const TextStyle(color: Palette.text, fontWeight: FontWeight.w600),
    ),
    dividerTheme: const DividerThemeData(color: Palette.line, space: 1),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: Palette.surface,
      showDragHandle: true,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(28))),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Palette.surface2,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
    ),
    appBarTheme: const AppBarTheme(backgroundColor: Palette.bg, surfaceTintColor: Colors.transparent, centerTitle: false),
  );
}

final _egp = NumberFormat.decimalPattern('en');
String egp(num v) => 'EGP ${_egp.format(v)}';
String num0(num v) => _egp.format(v);
String compact(num v) => v >= 1000 ? '${(v / 1000).toStringAsFixed(v % 1000 == 0 ? 0 : 1)}k' : '$v';

String ago(DateTime? t) {
  if (t == null) return 'unknown';
  final d = DateTime.now().difference(t);
  if (d.inMinutes < 1) return 'just now';
  if (d.inMinutes < 60) return '${d.inMinutes} min ago';
  if (d.inHours < 24) return '${d.inHours} h ago';
  return '${d.inDays} d ago';
}
