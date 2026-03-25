# frozen_string_literal: true

source "https://rubygems.org"

ruby ">= 3.2.0"

gem "rails", "~> 8.0.0"
gem "propshaft"
gem "sqlite3", ">= 2.1"
gem "puma", ">= 6.0"
gem "bootsnap", require: false
gem "faraday"
gem "csv"
gem "dotenv-rails", groups: %i[development test]

group :development, :test do
  gem "debug", platforms: %i[mri mingw x64_mingw]
end

group :development do
  gem "web-console"
end
