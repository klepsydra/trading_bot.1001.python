# frozen_string_literal: true

module Trading
  class Runner
    def initialize(broker: Broker.new, risk: nil, trade_logger: nil)
      @broker = broker
      @risk = risk || RiskManager.new(@broker)
      @tlog = trade_logger || TradeLogger.new
    end

    def tick
      unless @broker.market_open?
        Rails.logger.debug { "Market closed — skipping tick." }
        return
      end

      unless within_trading_window?
        Rails.logger.info("Outside trading window — skipping.")
        return
      end

      if @risk.daily_drawdown_breached?
        Rails.logger.warn("Trading HALTED for the day (drawdown limit reached).")
        return
      end

      positions = @broker.positions
      cfg = Trading.config

      cfg[:ticker_pairs].each do |base_symbol, meta|
        m = meta.with_indifferent_access
        process_pair(base_symbol.to_s, m[:etf].to_s, positions)
      end
    end

    private

    def within_trading_window?
      cfg = Trading.config
      now = Time.zone.now
      after_open = [now.hour, now.min] >= [cfg[:market_open_hour], cfg[:market_open_minute]]
      before_close = [now.hour, now.min] <= [cfg[:market_close_hour], cfg[:market_close_minute]]
      after_open && before_close
    end

    def process_pair(base_symbol, etf_symbol, positions)
      cfg = Trading.config
      bars = @broker.daily_bars(base_symbol, n_days: cfg[:historical_bars])
      if bars.nil? || bars.length < 25
        Rails.logger.warn("#{base_symbol}: not enough bars (#{bars&.length || 0}) — skipping")
        return
      end

      sig = Signals.compute(bars, symbol: base_symbol)
      action = sig[:action]
      etf_price = @broker.latest_price(etf_symbol)
      vol = Signals.compute_volatility(bars)
      existing = positions[etf_symbol]

      case action
      when "BUY"
        if existing.present?
          Rails.logger.info("HOLD | #{base_symbol} → #{etf_symbol} | score=#{format('%.4f', sig[:score])} (already long)")
        else
          shares = @risk.calc_position_size(signal_score: sig[:score], entry_price: etf_price, volatility: vol)
          if @risk.pre_trade_check(etf_symbol, shares, etf_price)
            order = @broker.place_bracket_order(symbol: etf_symbol, qty: shares, side: :buy, entry_price: etf_price)
            sl = Trading.config[:stop_loss_pct].to_f
            tp = Trading.config[:take_profit_pct].to_f
            @tlog.record(
              base_symbol: base_symbol,
              etf_symbol: etf_symbol,
              action: "BUY",
              shares: shares,
              entry_price: etf_price,
              stop_price: (etf_price * (1 - sl)).round(2),
              take_profit_price: (etf_price * (1 + tp)).round(2),
              signal_score: sig[:score],
              z_score: sig[:z_score],
              rsi_signal: sig[:rsi_signal],
              ema_signal: sig[:ema_signal],
              vol_conf: sig[:vol_conf],
              portfolio_value: @broker.portfolio_value,
              order_id: order["id"]
            )
          end
        end
      when "SELL"
        if existing.nil?
          Rails.logger.info("HOLD | #{base_symbol} → #{etf_symbol} | score=#{format('%.4f', sig[:score])} (flat)")
        else
          @broker.close_position(etf_symbol)
          qty = existing["qty"].to_i
          @tlog.record(
            base_symbol: base_symbol,
            etf_symbol: etf_symbol,
            action: "SELL/CLOSE",
            shares: qty,
            entry_price: etf_price,
            stop_price: nil,
            take_profit_price: nil,
            signal_score: sig[:score],
            z_score: sig[:z_score],
            rsi_signal: sig[:rsi_signal],
            ema_signal: sig[:ema_signal],
            vol_conf: sig[:vol_conf],
            portfolio_value: @broker.portfolio_value,
            order_id: nil
          )
        end
      else
        Rails.logger.info("HOLD | #{base_symbol} → #{etf_symbol} | score=#{format('%.4f', sig[:score])}")
      end
    rescue StandardError => e
      Rails.logger.error("Error processing pair #{base_symbol}→#{etf_symbol}: #{e}\n#{e.backtrace&.first(8)&.join("\n")}")
    end
  end
end
