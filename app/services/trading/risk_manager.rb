# frozen_string_literal: true

module Trading
  class RiskManager
    def initialize(broker, store: DailyDrawdownStore.new)
      @broker = broker
      @store = store
    end

    def daily_drawdown_breached?
      @store.refresh_start_of_day!(@broker.portfolio_value)
      start_val = @store.start_of_day_value
      return false if start_val.nil? || start_val <= 0

      current = @broker.portfolio_value
      drawdown = (start_val - current) / start_val
      limit = Trading.config[:max_daily_drawdown_pct].to_f
      if drawdown >= limit
        Rails.logger.warn(
          "DAILY DRAWDOWN HALT: #{format('%.2f', drawdown * 100)}% drawdown (limit #{format('%.2f', limit * 100)}%)"
        )
        return true
      end
      false
    end

    def calc_position_size(signal_score:, entry_price:, volatility:)
      cfg = Trading.config
      portfolio_value = @broker.portfolio_value
      max_dollar = portfolio_value * cfg[:max_portfolio_alloc_pct].to_f

      kelly_scalar = cfg[:kelly_fraction].to_f * [signal_score.abs / 1.0, 1.0].min
      vol_damper = volatility.positive? ? [0.02 / volatility, 1.0].min : 1.0

      dollar_size = portfolio_value * kelly_scalar * vol_damper
      dollar_size = [dollar_size, max_dollar].min
      shares = (dollar_size / entry_price).to_i

      Rails.logger.info(
        "SIZING | portfolio=$#{portfolio_value.to_i} kelly=#{format('%.3f', kelly_scalar)} vol_damper=#{format('%.3f', vol_damper)} dollar=$#{dollar_size.to_i} shares=#{shares} @ $#{format('%.2f', entry_price)}"
      )
      [shares, 0].max
    end

    def pre_trade_check(symbol, shares, entry_price)
      cfg = Trading.config
      if shares <= 0
        Rails.logger.warn("PRE-TRADE REJECT | #{symbol} | shares=#{shares} (zero)")
        return false
      end

      buying_power = @broker.buying_power
      required = shares * entry_price
      if required > buying_power
        Rails.logger.warn("PRE-TRADE REJECT | #{symbol} | need $#{required.to_i} but buying power $#{buying_power.to_i}")
        return false
      end

      portfolio_value = @broker.portfolio_value
      alloc_pct = required / portfolio_value
      if alloc_pct > cfg[:max_portfolio_alloc_pct].to_f
        Rails.logger.warn(
          "PRE-TRADE REJECT | #{symbol} | alloc #{format('%.1f', alloc_pct * 100)}% exceeds limit #{format('%.1f', cfg[:max_portfolio_alloc_pct].to_f * 100)}%"
        )
        return false
      end

      Rails.logger.info("PRE-TRADE OK | #{symbol} | #{shares} shares @ $#{format('%.2f', entry_price)}")
      true
    end
  end
end
