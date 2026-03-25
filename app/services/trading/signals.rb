# frozen_string_literal: true

module Trading
  module Signals
    module_function

    def compute(bars, symbol: "")
      cfg = Trading.config
      w = cfg[:signal_weights].with_indifferent_access

      z = compute_zscore(bars, cfg[:zscore_lookback])
      rsi_sig = compute_rsi(bars, cfg[:rsi_period], cfg[:rsi_overbought], cfg[:rsi_oversold])
      ema_sig = compute_ema_signal(bars, cfg[:ema_fast], cfg[:ema_slow])
      vol_conf = compute_volume_confidence(bars, cfg[:volume_spike_multiplier])

      directional = (w[:zscore] * z) + (w[:rsi] * rsi_sig) + (w[:ema] * ema_sig)
      vw = w[:volume]
      score = (directional * (1 - vw)) + (directional * vol_conf * vw)

      action =
        if score >= cfg[:buy_threshold]
          "BUY"
        elsif score <= cfg[:sell_threshold]
          "SELL"
        else
          "HOLD"
        end

      result = {
        symbol: symbol,
        score: score.round(4),
        action: action,
        z_score: z.round(4),
        rsi_signal: rsi_sig.round(4),
        ema_signal: ema_sig.round(4),
        vol_conf: vol_conf.round(4)
      }

      Rails.logger.info(
        "SIGNAL | #{symbol} | score=#{format('%.4f', score)} action=#{action} | z=#{format('%.3f', z)} rsi=#{format('%.3f', rsi_sig)} ema=#{format('%.3f', ema_sig)} vol=#{format('%.3f', vol_conf)}"
      )
      result
    end

    def compute_zscore(bars, lookback)
      closes = bars.map { |b| b[:close].to_f }
      return 0.0 if closes.length < lookback + 1

      returns = []
      (1...closes.length).each do |i|
        returns << Math.log(closes[i] / closes[i - 1])
      end
      window = returns.last(lookback)
      return 0.0 if window.empty?

      mu = window.sum / window.length
      variance = window.sum { |r| (r - mu)**2 } / (window.length - 1)
      sigma = Math.sqrt(variance)
      return 0.0 if sigma.zero?

      today_return = returns.last
      z = (today_return - mu) / sigma
      z = [[z, -3.0].max, 3.0].min
      z / 3.0
    end

    def compute_rsi(bars, period, overbought, oversold)
      closes = bars.map { |b| b[:close].to_f }
      return 0.0 if closes.length < period + 1

      deltas = closes.each_cons(2).map { |a, b| b - a }
      gains = deltas.map { |d| d.positive? ? d : 0.0 }
      losses = deltas.map { |d| d.negative? ? -d : 0.0 }
      avg_gain = gains.last(period).sum / period
      avg_loss = losses.last(period).sum / period

      rsi =
        if avg_loss.zero?
          100.0
        else
          rs = avg_gain / avg_loss
          100 - (100 / (1 + rs))
        end

      if rsi >= overbought
        -((rsi - overbought) / (100 - overbought))
      elsif rsi <= oversold
        (oversold - rsi) / oversold
      else
        midpoint = (overbought + oversold) / 2.0
        ((rsi - midpoint) / (midpoint - oversold)) * -0.3
      end
    end

    def compute_ema_signal(bars, fast_span, slow_span)
      closes = bars.map { |b| b[:close].to_f }
      return 0.0 if closes.length < slow_span + 1

      ema_fast = ema_last(closes, fast_span)
      ema_slow = ema_last(closes, slow_span)
      pct_gap = (ema_fast - ema_slow) / ema_slow
      sign = pct_gap.positive? ? 1.0 : (pct_gap.negative? ? -1.0 : 0.0)
      sign * [pct_gap.abs * 50, 1.0].min
    end

    def ema_last(values, span)
      alpha = 2.0 / (span + 1)
      ema = values.first
      values.drop(1).each do |x|
        ema = (x * alpha) + (ema * (1 - alpha))
      end
      ema
    end

    def compute_volume_confidence(bars, multiplier)
      vols = bars.map { |b| b[:volume].to_f }
      return 0.5 if vols.length < 21

      avg_vol = vols[-21..-2].sum / 20.0
      today_vol = vols.last
      return 0.5 if avg_vol.zero?

      ratio = today_vol / avg_vol
      [ratio / (2 * multiplier), 1.0].min
    end

    def compute_volatility(bars)
      closes = bars.map { |b| b[:close].to_f }
      return 0.01 if closes.length < 2

      returns = []
      (1...closes.length).each do |i|
        returns << Math.log(closes[i] / closes[i - 1])
      end
      window = returns.last(20)
      return 0.01 if window.length < 2

      mu = window.sum / window.length
      variance = window.sum { |r| (r - mu)**2 } / (window.length - 1)
      Math.sqrt(variance)
    end
  end
end
