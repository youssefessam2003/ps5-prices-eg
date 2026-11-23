import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ps5_prices/data/repo.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Map<String, dynamic> bundled;

  setUp(() async {
    bundled = jsonDecode(await rootBundle.loadString('assets/data/latest.json')) as Map<String, dynamic>;
    SharedPreferences.setMockInitialValues({});
  });

  Map<String, dynamic> dated(int minutes, {bool oldDirectory = false}) => {
        ...bundled,
        'generated_at': DateTime.parse(bundled['generated_at']).add(Duration(minutes: minutes)).toIso8601String(),
        if (oldDirectory) 'directory': [],
      };

  Future<Repo> load(Map<String, dynamic> network) => http.runWithClient(() async {
        final repo = Repo();
        await repo.init();
        return repo;
      }, () => MockClient((request) async => request.url.path.endsWith('history.json')
          ? http.Response('{}', 404)
          : http.Response(jsonEncode(network), 200, headers: {'content-type': 'application/json; charset=utf-8'})));

  test('updated APK keeps newer bundled sources over old cache and server', () async {
    SharedPreferences.setMockInitialValues({'cache_latest': jsonEncode(dated(-60, oldDirectory: true))});
    final repo = await load(dated(-30, oldDirectory: true));
    expect(repo.origin, LoadOrigin.bundled);
    expect(repo.snapshot!.sources.length, (bundled['directory'] as List).length);
    expect(repo.snapshot!.sources.any((s) => s.id == 'gamesspot'), isTrue);
    expect(repo.snapshot!.sources.any((s) => s.id == 'gamerscolony'), isTrue);
    expect(repo.error, contains('older data'));
    final prefs = await SharedPreferences.getInstance();
    expect(jsonDecode(prefs.getString('cache_latest')!)['directory'], isEmpty);
    repo.dispose();
  });

  test('a newer cached snapshot survives an older server response', () async {
    final cache = dated(30);
    SharedPreferences.setMockInitialValues({'cache_latest': jsonEncode(cache)});
    final repo = await load(dated(10));
    expect(repo.origin, LoadOrigin.cache);
    expect(repo.snapshot!.generatedAt, DateTime.parse(cache['generated_at']));
    expect(repo.error, contains('older data'));
    repo.dispose();
  });

  test('new server data replaces the bundle and is cached', () async {
    final network = dated(30);
    final repo = await load(network);
    expect(repo.origin, LoadOrigin.network);
    expect(repo.snapshot!.generatedAt, DateTime.parse(network['generated_at']));
    expect(repo.error, isNull);
    final prefs = await SharedPreferences.getInstance();
    expect(jsonDecode(prefs.getString('cache_latest')!)['generated_at'], network['generated_at']);
    repo.dispose();
  });

  test('damaged cached JSON falls back to the updated bundle', () async {
    SharedPreferences.setMockInitialValues({'cache_latest': 'broken JSON'});
    final repo = await load(dated(-30));
    expect(repo.origin, LoadOrigin.bundled);
    expect(repo.snapshot!.listings.length, (bundled['listings'] as List).length);
    repo.dispose();
  });
}
