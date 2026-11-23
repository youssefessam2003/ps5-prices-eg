import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';
import 'price_check.dart';

/// Where the daily collector publishes its JSON files.
const publishedDataUrl =
    'https://raw.githubusercontent.com/youssefessam2003/ps5-prices-eg/main/data';
const defaultDataUrl = String.fromEnvironment(
  'PRICE_DATA_URL',
  defaultValue: publishedDataUrl,
);

enum LoadOrigin { network, cache, bundled }

class Repo extends ChangeNotifier {
  Repo({
    String? collectorUrl,
    String? collectorToken,
    this.pollInterval = const Duration(seconds: 2),
  }) : _collectorUrl =
           collectorUrl ?? const String.fromEnvironment('COLLECTOR_URL'),
       _collectorToken =
           collectorToken ?? const String.fromEnvironment('COLLECTOR_TOKEN');

  final String _collectorUrl, _collectorToken;
  final Duration pollInterval;
  Future<void>? _refreshFuture;
  PriceCheck? priceCheck;
  bool get liveRefreshEnabled =>
      _collectorUrl.isNotEmpty &&
      _collectorToken.isNotEmpty &&
      dataUrl == defaultDataUrl;
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
    if (dataUrl == publishedDataUrl && defaultDataUrl != publishedDataUrl) {
      dataUrl = defaultDataUrl;
      await _prefs.setString('dataUrl', dataUrl);
    }
    model = _prefs.getString('model') == 'disc' ? Model.disc : Model.digital;
    includeBundles = _prefs.getBool('bundles') ?? false;
    includeUnconfirmedSlim = _prefs.getBool('unconfirmed') ?? false;
    includeManual = _prefs.getBool('manualOn') ?? true;
    manual = [
      for (final e in jsonDecode(_prefs.getString('manual') ?? '[]') as List)
        ManualEntry.fromJson(e),
    ];
    final cachedL = _prefs.getString('cache_latest');
    final cachedH = _prefs.getString('cache_history');
    if (cachedL != null) {
      try {
        _set(
          jsonDecode(cachedL),
          cachedH == null ? null : jsonDecode(cachedH),
          LoadOrigin.cache,
        );
      } catch (_) {
        // A damaged cache must not prevent an updated app from opening.
      }
    }
    if (dataUrl == defaultDataUrl || snapshot == null) {
      try {
        final l = await rootBundle.loadString('assets/data/latest.json');
        final h = await rootBundle.loadString('assets/data/history.json');
        _set(
          jsonDecode(l),
          jsonDecode(h),
          LoadOrigin.bundled,
          requireFreshest: true,
        );
      } catch (_) {}
    }
    notifyListeners();
    await refresh(collect: false);
  }

  bool _set(
    Map<String, dynamic> l,
    Map<String, dynamic>? h,
    LoadOrigin o, {
    bool requireFreshest = false,
  }) {
    final incoming = Snapshot.parse(l, h);
    if (requireFreshest && snapshot != null) {
      final currentAt =
          snapshot!.generatedAt ?? DateTime.tryParse(snapshot!.date);
      final incomingAt =
          incoming.generatedAt ?? DateTime.tryParse(incoming.date);
      if (currentAt != null &&
          (incomingAt == null || incomingAt.isBefore(currentAt))) {
        return false;
      }
    }
    snapshot = incoming;
    origin = o;
    return true;
  }

  /// A user refresh starts/joins a fresh collection. Startup only loads existing
  /// data and reconnects to a job already in progress.
  Future<void> refresh({bool collect = true}) => _refreshFuture ??= _refresh(
    collect: collect,
  ).whenComplete(() => _refreshFuture = null);

  Future<dynamic> _liveRequest(String path, {bool post = false}) async {
    final uri = Uri.parse('$_collectorUrl$path');
    final headers = {'Authorization': 'Bearer $_collectorToken'};
    final response =
        await (post
                ? http.post(uri, headers: headers)
                : http.get(uri, headers: headers))
            .timeout(const Duration(seconds: 15));
    if (response.statusCode == 401) {
      throw const _PriceCheckError(
        'The price service did not recognize this app. Reconnect it on the computer.',
      );
    }
    if (response.statusCode != 200 && response.statusCode != 202) {
      throw const _PriceCheckError(
        'The price service could not complete this request. Please retry.',
      );
    }
    return jsonDecode(utf8.decode(response.bodyBytes));
  }

  Future<void> _followCheck(Map<String, dynamic> json) async {
    priceCheck = PriceCheck.fromJson(json);
    final deadline = DateTime.now().add(const Duration(minutes: 65));
    while (priceCheck!.running) {
      await _prefs.setString('activePriceCheck', priceCheck!.id);
      notifyListeners();
      if (DateTime.now().isAfter(deadline)) {
        throw const _PriceCheckError(
          'The check is taking longer than expected. Tap Refresh to reconnect to it.',
        );
      }
      await Future<void>.delayed(pollInterval);
      priceCheck = PriceCheck.fromJson(
        await _liveRequest('/api/jobs/${priceCheck!.id}'),
      );
    }
    await _prefs.remove('activePriceCheck');
    if (!priceCheck!.successful) throw _PriceCheckError(priceCheck!.summary);
  }

  Future<void> _refresh({required bool collect}) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      if (liveRefreshEnabled) {
        if (collect) {
          await _followCheck(await _liveRequest('/api/refresh', post: true));
        } else {
          await _downloadPrices();
          var active = await _liveRequest('/api/jobs/active');
          final saved = _prefs.getString('activePriceCheck');
          if (active == null && saved != null) {
            active = await _liveRequest('/api/jobs/$saved');
          }
          if (active == null) return;
          await _followCheck(active);
        }
      }
      await _downloadPrices();
    } catch (e) {
      error = e is _PriceCheckError
          ? e.message
          : liveRefreshEnabled
          ? 'Could not reach the price collector. Keep the computer on and connected to this phone, then retry. Previous prices are still shown.'
          : 'Could not reach the price server. Showing prices already on this phone.';
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> _downloadPrices() async {
    String l;
    String? h;
    if (liveRefreshEnabled) {
      final data = await _liveRequest('/api/snapshot') as Map<String, dynamic>;
      l = jsonEncode(data['latest']);
      h = jsonEncode(data['history']);
    } else {
      final bust = DateTime.now().millisecondsSinceEpoch;
      final res = await Future.wait([
        http.get(Uri.parse('$dataUrl/latest.json?t=$bust')),
        http.get(Uri.parse('$dataUrl/history.json?t=$bust')),
      ]).timeout(const Duration(seconds: 25));
      if (res[0].statusCode != 200) {
        throw 'Server answered ${res[0].statusCode}';
      }
      l = utf8.decode(res[0].bodyBytes);
      h = res[1].statusCode == 200 ? utf8.decode(res[1].bodyBytes) : null;
    }
    final accepted = _set(
      jsonDecode(l),
      h == null ? null : jsonDecode(h),
      LoadOrigin.network,
      requireFreshest: dataUrl == defaultDataUrl,
    );
    if (!accepted) {
      error =
          'The price server has older data. Showing newer prices already on this phone.';
      return;
    }
    error = null;
    await _prefs.setString('cache_latest', l);
    if (h != null) await _prefs.setString('cache_history', h);
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
    await refresh(collect: false);
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
    await _prefs.setString(
      'manual',
      jsonEncode([for (final e in manual) e.toJson()]),
    );
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
        .where(
          (l) =>
              l.inStock &&
              l.model == mm &&
              (b || !l.bundle) &&
              (includeUnconfirmedSlim || l.slimConfirmed),
        )
        .toList()
      ..sort((a, b) => a.price.compareTo(b.price));
  }

  Stats? stats({Model? m}) => Stats.of(offers(m: m));
}

class _PriceCheckError implements Exception {
  final String message;
  const _PriceCheckError(this.message);
}
