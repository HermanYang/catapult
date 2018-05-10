# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pandas  # pylint: disable=import-error


COLUMNS = (
    'test_suite',  # string: benchmark name ('loading.mobile')
    'measurement',  # string: metric name ('timeToFirstContentfulPaint')
    'bot',  # string: master/builder name ('ChromiumPerf.android-nexus5')
    'test_case',  # string: story name ('Wikipedia')
    'point_id',  # int: monotonically increasing value for time series axis
    'value',  # float: value recorded for test_path at given point_id
    'timestamp',  # np.datetime64: when the value got stored on dashboard
    'commit_pos',  # int: chromium commit position
    'chromium_rev',  # string: git hash of chromium revision
    'clank_rev',  # string: git hash of clank revision
)
INDEX = COLUMNS[:5]

TEST_PATH_PARTS = (
    'master', 'builder', 'test_suite', 'measurement', 'test_case')

# This query finds the most recent point_id for a given test_path (i.e. fixed
# test_suite, measurement, bot, and test_case values).
_GET_MOST_RECENT_QUERY = (
    'SELECT * FROM timeseries WHERE %s ORDER BY timestamp DESC LIMIT 1'
    % ' AND '.join('%s=?' % c for c in INDEX[:-1]))


def _ParseConfigFromTestPath(test_path):
  values = test_path.split('/', len(TEST_PATH_PARTS))
  config = dict(zip(TEST_PATH_PARTS, values))
  config['bot'] = '%s/%s' % (config.pop('master'), config.pop('builder'))
  return config


def DataFrameFromJson(data):
  config = _ParseConfigFromTestPath(data['test_path'])
  timeseries = data['timeseries']
  # The first element in timeseries list contains header with column names.
  header = timeseries[0]
  rows = []

  # Remaining elements contain the values for each row.
  for values in timeseries[1:]:
    row = config.copy()
    row.update(zip(header, values))
    row['point_id'] = row['revision']
    row['commit_pos'] = int(row['r_commit_pos'])
    row['chromium_rev'] = row['r_chromium']
    row['clank_rev'] = row.get('r_clank', None)
    rows.append(tuple(row[k] for k in COLUMNS))

  df = pandas.DataFrame.from_records(rows, index=INDEX, columns=COLUMNS)
  df['timestamp'] = pandas.to_datetime(df['timestamp'])
  return df


def HasTable(con):
  return pandas.io.sql.has_table('timeseries', con)


def GetMostRecentPoint(con, test_path):
  """Find the record for the most recent data point on the given test_path.

  Returns:
    A pandas.Series with the record if found, or None otherwise.
  """
  config = _ParseConfigFromTestPath(test_path)
  params = tuple(config[c] for c in INDEX[:-1])
  df = pandas.read_sql(
      _GET_MOST_RECENT_QUERY, con, params=params, parse_dates=['timestamp'])
  return df.iloc[0] if not df.empty else None