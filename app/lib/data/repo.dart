import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

/// Where the daily collector publishes its JSON files.
const defaultDataUrl = 'https://raw.githubusercontent.com/youssefessam2003/ps5-prices-eg/main/data';

enum LoadOrigin { network, cache, bundled }

class Repo extends ChangeNotifier {
  Snapshot? snapshot;
  LoadOrigin? origin;
  String? error;
  bool loading = false;
  String dataUrl = defaultDataUrl;
  List<ManualEntry> manual = [];

  // view filters shared by all tabs
  Model model = Model.digital;
  bool includeBundles = false;
  bool includeUnconfirmedSlim = false;
  bool includeManual = true;

  late SharedPreferences _prefs;

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    dataUrl = _prefs.getString('dataUrl') ?? defaultDataUrl;
    model = _prefs.getString('model') == 'disc' ? Model.disc : Model.digital;
    includeBundles = _prefs.getBool('bundles') ?? false;
    includeUnconfirmedSlim = _prefs.getBool('unconfirmed') ?? false;
    includeManual = _prefs.getBool('manualOn') ?? true;
    manual = [
      for (final e in jsonDecode(_prefs.getString('manual') ?? '[]') as List) ManualEntry.fromJson(e),
    ];
    final cachedL = _prefs.getString('cache_latest');
    final cachedH = _prefs.getString('cache_history');
    if (cachedL != null) {
      _set(jsonDecode(cachedL), cachedH == null ? null : jsonDecode(cachedH), LoadOrigin.cache);
    } else {
      try {
        final l = await rootBundle.loadString('assets/data/latest.json');
        final h = await rootBundle.loadString('assets/data/history.json');
        _set(jsonDecode(l), jsonDecode(h), LoadOrigin.bundled);
      } catch (_) {}
    }
    notifyListeners();
    refresh();
  }

  void _set(Map<String, dynamic> l, Map<String, dynamic>? h, LoadOrigin o) {
    snapshot = Snapshot.parse(l, h);
    origin = o;
  }

  Future<void> refresh() async {
    if (loading) return;
    loading = true;
    error = null;
    notifyListeners();
    try {
      final bust = DateTime.now().millisecondsSinceEpoch;
      final res = await Future.wait([
        http.get(Uri.parse('$dataUrl/latest.json?t=$bust')),
        http.get(Uri.parse('$dataUrl/history.json?t=$bust')),
      ]).timeout(const Duration(seconds: 25));
      if (res[0].statusCode != 200) throw 'Server answered ${res[0].statusCode}';
      final l = utf8.decode(res[0].bodyBytes);
      final h = res[1].statusCode == 200 ? utf8.decode(res[1].bodyBytes) : null;
      _set(jsonDecode(l), h == null ? null : jsonDecode(h), LoadOrigin.network);
      await _prefs.setString('cache_latest', l);
      if (h != null) await _prefs.setString('cache_history', h);
    } catch (e) {
      error = 'Could not reach the price server ($e). Showing ${origin == LoadOrigin.cache ? 'your last download' : 'built-in data'}.';
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  // ---------- filters ----------
  void setModel(Model m) {
    model = m;
    _prefs.setString('model', m.name);
    notifyListeners();
  }

  void setBundles(bool v) {
    includeBundles = v;
    _prefs.setBool('bundles', v);
    notifyListeners();
  }

  void setUnconfirmed(bool v) {
    includeUnconfirmedSlim = v;
    _prefs.setBool('unconfirmed', v);
    notifyListeners();
  }

  void setManualOn(bool v) {
    includeManual = v;
    _prefs.setBool('manualOn', v);
    notifyListeners();
  }

  Future<void> setDataUrl(String url) async {
    dataUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    await _prefs.setString('dataUrl', dataUrl);
    await refresh();
  }

  // ---------- manual prices ----------
  Future<void> addManual(ManualEntry e) async {
    manual.add(e);
    await _saveManual();
  }

  Future<void> removeManual(String id) async {
    manual.removeWhere((e) => e.id == id);
    await _saveManual();
  }

  Future<void> _saveManual() async {
    await _prefs.setString('manual', jsonEncode([for (final e in manual) e.toJson()]));
    notifyListeners();
  }

  /// Manual prices count as "current" for 3 days after you log them.
  List<Listing> get recentManual => [
        for (final e in manual)
          if (DateTime.now().difference(e.at).inHours < 72) e.toListing(),
      ];

  /// In-stock offers for the selected model, after the user's filters.
  List<Listing> offers({Model? m, bool? bundles}) {
    final mm = m ?? model;
    final b = bundles ?? includeBundles;
    final all = [...?snapshot?.listings, if (includeManual) ...recentManual];
    return all
        .where((l) =>
            l.inStock &&
            l.model == mm &&
            (b || !l.bundle) &&
            (includeUnconfirmedSlim || l.slimConfirmed))
        .toList()
      ..sort((a, b) => a.price.compareTo(b.price));
  }

  Stats? stats({Model? m}) => Stats.of(offers(m: m));
}
