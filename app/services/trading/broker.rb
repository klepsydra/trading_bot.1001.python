# frozen_string_literal: true

require "erb"
require "json"

module Trading
  class Broker
    class Error < StandardError; end

    def initialize
      raise Error, "Set ALPACA_API_KEY and ALPACA_SECRET_KEY" if Trading.alpaca_api_key.blank? || Trading.alpaca_secret_key.blank?

      @trading_url = Trading.config[:paper_trading] ? "https://paper-api.alpaca.markets" : "https://api.alpaca.markets"
      @data_url = "https://data.alpaca.markets"
    end

    def trading_conn
      @trading_conn ||= Faraday.new(url: @trading_url) do |f|
        f.request :url_encoded
        f.adapter Faraday.default_adapter
        f.headers["APCA-API-KEY-ID"] = Trading.alpaca_api_key
        f.headers["APCA-API-SECRET-KEY"] = Trading.alpaca_secret_key
      end
    end

    def data_conn
      @data_conn ||= Faraday.new(url: @data_url) do |f|
        f.request :url_encoded
        f.adapter Faraday.default_adapter
        f.headers["APCA-API-KEY-ID"] = Trading.alpaca_api_key
        f.headers["APCA-API-SECRET-KEY"] = Trading.alpaca_secret_key
      end
    end

    def get_account
      parse(trading_conn.get("/v2/account"))
    end

    def portfolio_value
      get_account["portfolio_value"].to_f
    end

    def buying_power
      get_account["buying_power"].to_f
    end

    def positions
      rows = parse_array(trading_conn.get("/v2/positions"))
      rows.index_by { |p| p["symbol"] }
    end

    def position(symbol)
      positions[symbol]
    end

    # Returns array of bar hashes: { time:, open:, high:, low:, close:, volume: }
    def daily_bars(symbol, n_days: 60)
      start = (Time.now.utc - (n_days + 15).days).iso8601
      resp = data_conn.get(
        "/v2/stocks/#{ERB::Util.url_encode(symbol)}/bars",
        {
          timeframe: "1Day",
          start: start,
          limit: n_days + 30,
          adjustment: "raw",
          feed: "sip"
        }
      )
      body = parse(resp)
      bars = body["bars"] || []
      normalized = bars.map { |b| normalize_bar(b) }
      normalized.last(n_days)
    end

    def latest_price(symbol)
      resp = data_conn.get("/v2/stocks/#{ERB::Util.url_encode(symbol)}/quotes/latest")
      body = parse(resp)
      quote = body["quote"] || {}
      (quote["ap"] || quote["ask_price"] || quote["bp"] || quote["bid_price"]).to_f
    end

    def market_open?
      body = parse(trading_conn.get("/v2/clock"))
      body["is_open"] == true
    end

    # side: :buy or :sell
    def place_bracket_order(symbol:, qty:, side:, entry_price:)
      cfg = Trading.config
      sl = cfg[:stop_loss_pct].to_f
      tp = cfg[:take_profit_pct].to_f

      stop_price, profit_price =
        if side.to_s == "buy"
          [ (entry_price * (1 - sl)).round(2), (entry_price * (1 + tp)).round(2) ]
        else
          [ (entry_price * (1 + sl)).round(2), (entry_price * (1 - tp)).round(2) ]
        end

      payload = {
        symbol: symbol,
        qty: qty.to_i,
        side: side.to_s,
        type: "market",
        time_in_force: "day",
        order_class: "bracket",
        take_profit: { limit_price: profit_price.to_s },
        stop_loss: { stop_price: stop_price.to_s }
      }

      resp = trading_conn.post("/v2/orders") do |req|
        req.headers["Content-Type"] = "application/json"
        req.body = JSON.generate(payload)
      end
      order = parse(resp)
      Rails.logger.info(
        "ORDER SUBMITTED | #{side.to_s.upcase} #{symbol} #{qty.to_i} @ ~#{entry_price} | SL=#{stop_price} TP=#{profit_price} | id=#{order['id']}"
      )
      order
    end

    def close_position(symbol)
      resp = trading_conn.delete("/v2/positions/#{ERB::Util.url_encode(symbol)}")
      Rails.logger.info("POSITION CLOSED | #{symbol}")
      parse_optional(resp)
    end

    def cancel_all_orders
      resp = trading_conn.delete("/v2/orders")
      Rails.logger.info("All open orders cancelled.")
      parse_optional(resp)
    end

    private

    def parse(resp)
      raise Error, "Alpaca #{resp.status}: #{resp.body}" unless resp.success?

      body = resp.body.to_s
      body.present? ? JSON.parse(body) : {}
    end

    def parse_optional(resp)
      raise Error, "Alpaca #{resp.status}: #{resp.body}" unless resp.success?

      body = resp.body.to_s
      body.present? ? JSON.parse(body) : {}
    end

    def parse_array(resp)
      raise Error, "Alpaca #{resp.status}: #{resp.body}" unless resp.success?

      body = resp.body.to_s
      body.present? ? JSON.parse(body) : []
    end

    def normalize_bar(b)
      {
        time: b["t"],
        open: b["o"].to_f,
        high: b["h"].to_f,
        low: b["l"].to_f,
        close: b["c"].to_f,
        volume: b["v"].to_f
      }
    end
  end
end
