#!/usr/bin/env lua
--- The record says what it is.
---@param name string the value decides the size
local function f(name)
  -- The flag decides the target.
  local s = "-- The text says so."
  local t = [[
-- The value knows the size.
]]
  local u = [==[ ]] -- The value knows. ]==]
  --[[ The option wants a list. ]]
  --[==[
  The parser reads each field.
  The config decides the order.
  ]==]
  return s .. t .. u
end
