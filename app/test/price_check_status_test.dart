import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ps5_prices/data/price_check.dart';
import 'package:ps5_prices/data/repo.dart';
import 'package:ps5_prices/ui/price_check_status.dart';
import 'package:ps5_prices/ui/theme.dart';

void main() {
  testWidgets('progress stays readable with large text and disables repeat taps', (tester) async {
    final repo = Repo()..loading = true;
    repo.priceCheck = PriceCheck.fromJson({
      'id': 'test', 'status': 'running', 'completed': 12, 'total': 43,
      'current_source': 'Gamers Colony · PlayStation console store',
    });
    addTearDown(() => tester.binding.setSurfaceSize(null));
    for (final size in [const Size(375, 812), const Size(812, 375), const Size(1024, 768)]) {
      await tester.binding.setSurfaceSize(size);
      await tester.pumpWidget(MaterialApp(
        theme: buildTheme(),
        home: MediaQuery(
          data: MediaQueryData(size: size, textScaler: TextScaler.linear(2), disableAnimations: true),
          child: Scaffold(body: SafeArea(child: SingleChildScrollView(
            child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
              RefreshPricesButton(repo: repo), PriceCheckStatus(repo: repo),
            ])),
          ))),
        ),
      ));
      expect(tester.takeException(), isNull);
      expect(find.textContaining('12/43 sources checked'), findsOneWidget);
      expect(tester.widget<IconButton>(find.byType(IconButton)).onPressed, isNull);
      expect(tester.widget<LinearProgressIndicator>(find.byType(LinearProgressIndicator)).semanticsValue,
          '28%');
    }
    await tester.pumpWidget(const SizedBox.shrink());
    repo.dispose();
  });
}
