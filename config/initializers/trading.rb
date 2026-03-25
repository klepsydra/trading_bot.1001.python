# frozen_string_literal: true

module Trading
  mattr_accessor :config, :alpaca_api_key, :alpaca_secret_key

  self.config = Rails.application.config_for(:trading).deep_symbolize_keys

  self.alpaca_api_key = ENV["ALPACA_API_KEY"]
  self.alpaca_secret_key = ENV["ALPACA_SECRET_KEY"]
end
