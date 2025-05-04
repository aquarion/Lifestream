require "java"
require "rubygems"
require "jdbc/mysql"
include_class "com.mysql.jdbc.Driver"

class JdbcMysql
  def initialize(host = nil, username = nil, password = nil, db = nil, port = nil)
    host ||= "localhost"
    port ||= 3306

    address = "jdbc:mysql://#{host}:#{port}/#{db}"
    @connection = java.sql.DriverManager.getConnection(address, username, password)
  end

  def query(sql)
    resultSet = @connection.createStatement.executeQuery sql

    meta = resultSet.getMetaData
    column_count = meta.getColumnCount

    rows = []

    while resultSet.next
      res = {}

      (1..column_count).each do |i|
        name = meta.getColumnName i
        case meta.getColumnType i
        when java.sql.Types::INTEGER
          res[name] = resultSet.getInt name
        else
          res[name] = resultSet.getString name
        end
      end

      rows << res
    end
    rows
  end

  def preparedQuery(sql, values)

    statement = @connection.prepareStatement(sql)

    i = 1;

    values.each { |value|
      if value.class == String
        statement.setString(i, value)
      elsif value.class == Number
        statement.setFloat(i, value)
      else
        throw "Error converting " + value
      end
      i += 1
    }

    rs = statement.execute

    return rs

  end

end
