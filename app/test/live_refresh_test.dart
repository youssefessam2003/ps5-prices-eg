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
  late Map<String, dynamic> fresh;
  const jobId = '0123456789abcdef0123456789abcdef';
  const token = 'test-token-only';

  Map<String, dynamic> job(String status, {int completed = 0}) => {
        'id': jobId, 'status': status, 'total': 2, 'completed': completed,
        'current_source': 'Games Spot', 'succeeded': 1, 'failed': 1,
        if (status == 'failed') 'error': 'The price check was interrupted. Please retry.',
      };
  http.Response response(dynamic value, [int status = 200]) =>
      http.Response(jsonEncode(value), status, headers: {'content-type': 'application/json; charset=utf-8'});

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    bundled = jsonDecode(await rootBundle.loadString('assets/data/latest.json')) as Map<String, dynamic>;
    fresh = {...bundled, 'generated_at': DateTime.parse(bundled['generated_at']).add(const Duration(minutes: 10)).toIso8601String()};
  });

  Repo repo() => Repo(collectorUrl: 'http://127.0.0.1:8765', collectorToken: token, pollInterval: Duration.zero);

  test('Refresh starts one fresh job, shows progress and downloads only after completion', () async {
    var starts = 0, polls = 0;
    var done = false;
    await http.runWithClient(() async {
      final r = repo();
      await r.init();
      expect(starts, 0, reason: 'Opening the app must not silently start a full crawl');
      final seen = <int>[];
      r.addListener(() {
        if (r.priceCheck?.running == true) {
          seen.add(r.priceCheck!.completed);
          expect(r.snapshot!.generatedAt, DateTime.parse(bundled['generated_at']));
        }
      });
      final first = r.refresh();
      final duplicate = r.refresh();
      await Future.wait([first, duplicate]);
      expect(starts, 1);
      expect(seen, containsAll([0, 1]));
      expect(r.priceCheck!.summary, contains('1 unavailable'));
      expect(r.snapshot!.generatedAt, DateTime.parse(fresh['generated_at']));
      expect(r.loading, isFalse);
      expect(r.error, isNull);
      r.dispose();
    }, () => MockClient((request) async {
      expect(request.headers['Authorization'], 'Bearer $token');
      if (request.url.path == '/api/refresh') {
        expect(request.method, 'POST');
        starts++;
        return response(job('running'), 202);
      }
      if (request.url.path == '/api/jobs/active') return response(null);
      if (request.url.path == '/api/jobs/$jobId') {
        polls++;
        done = polls == 2;
        return response(job(done ? 'completed' : 'running', completed: polls));
      }
      expect(request.url.path, '/api/snapshot');
      return response({'latest': done ? fresh : bundled, 'history': {'days': [], 'listings': {}}});
    }));
  });

  test('reopening follows the active check without starting another scan', () async {
    var polls = 0;
    await http.runWithClient(() async {
      final r = repo();
      await r.init();
      expect(r.snapshot!.generatedAt, DateTime.parse(fresh['generated_at']));
      expect(r.priceCheck!.successful, isTrue);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('activePriceCheck'), isNull);
      r.dispose();
    }, () => MockClient((request) async {
      expect(request.method, 'GET');
      if (request.url.path == '/api/jobs/active') return response(job('running'));
      if (request.url.path == '/api/jobs/$jobId') {
        polls++;
        return response(job('completed', completed: 2));
      }
      return response({'latest': polls == 0 ? bundled : fresh, 'history': {'days': [], 'listings': {}}});
    }));
  });

  test('failed fresh check preserves previous prices and permits another attempt', () async {
    var starts = 0;
    await http.runWithClient(() async {
      final r = repo();
      await r.init();
      await r.refresh();
      expect(r.error, contains('interrupted'));
      expect(r.loading, isFalse);
      expect(r.snapshot!.generatedAt, DateTime.parse(bundled['generated_at']));
      await r.refresh();
      expect(starts, 2);
      expect(r.error, isNull);
      expect(r.snapshot!.generatedAt, DateTime.parse(fresh['generated_at']));
      r.dispose();
    }, () => MockClient((request) async {
      if (request.url.path == '/api/jobs/active') return response(null);
      if (request.url.path == '/api/refresh') {
        starts++;
        return response(job(starts == 1 ? 'failed' : 'completed', completed: 2), 202);
      }
      return response({'latest': starts == 2 ? fresh : bundled, 'history': {'days': [], 'listings': {}}});
    }));
  });
}
