# -*- coding: utf-8 -*-
"""
Test the Recorder object API

"""
from __future__ import print_function
import pywr.core
from pywr.core import Model, Input, Output, Scenario, AggregatedNode
import numpy as np
import pandas
import pytest
from numpy.testing import assert_allclose, assert_equal
from fixtures import simple_linear_model, simple_storage_model
from pywr.recorders import (NumpyArrayNodeRecorder, NumpyArrayStorageRecorder,
    AggregatedRecorder, CSVRecorder, TablesRecorder, TotalDeficitNodeRecorder,
    TotalFlowNodeRecorder, MeanFlowRecorder, NumpyArrayParameterRecorder,
    NumpyArrayIndexParameterRecorder, RollingWindowParameterRecorder, AnnualCountIndexParameterRecorder,
    RootMeanSquaredErrorNodeRecorder, MeanAbsoluteErrorNodeRecorder, MeanSquareErrorNodeRecorder,
    PercentBiasNodeRecorder, RMSEStandardDeviationRatioNodeRecorder, NashSutcliffeEfficiencyNodeRecorder,
    EventRecorder, Event, StorageThresholdRecorder, NodeThresholdRecorder, EventDurationRecorder,
    FlowDurationCurveRecorder, FlowDurationCurveDeviationRecorder, load_recorder)

from pywr.parameters import DailyProfileParameter, FunctionParameter, ArrayIndexedParameter
from helpers import load_model
import os


def test_numpy_recorder(simple_linear_model):
    """
    Test the NumpyArrayNodeRecorder
    """
    model = simple_linear_model
    otpt = model.nodes['Output']

    model.nodes['Input'].max_flow = 10.0
    otpt.cost = -2.0
    rec = NumpyArrayNodeRecorder(model, otpt)

    # test retrieval of recorder
    assert model.recorders['numpyarraynoderecorder.Output'] == rec
    # test changing name of recorder
    rec.name = 'timeseries.Output'
    assert model.recorders['timeseries.Output'] == rec
    with pytest.raises(KeyError):
        model.recorders['numpyarraynoderecorder.Output']

    model.run()

    assert rec.data.shape == (365, 1)
    assert np.all((rec.data - 10.0) < 1e-12)

    df = rec.to_dataframe()
    assert df.shape == (365, 1)
    assert np.all((df.values - 10.0) < 1e-12)


def test_numpy_recorder_from_json(simple_linear_model):
    """ Test loading NumpyArrayNodeRecorder from JSON style data """

    model = simple_linear_model

    data = {
        "type": "numpyarraynode",
        "node": "Output"
    }

    rec = load_recorder(model, data)
    assert isinstance(rec, NumpyArrayNodeRecorder)


def test_fdc_recorder():
    """
    Test the FlowDurationCurveRecorder
    """
    model = load_model("timeseries2.json")
    input = model.nodes['catchment1']

    percentiles = np.linspace(20., 100., 5)
    rec = FlowDurationCurveRecorder(model, input, percentiles, fdc_agg_func="max", agg_func="min")

    # test retrieval of recorder
    assert model.recorders['flowdurationcurverecorder.catchment1'] == rec
    # test changing name of recorder
    rec.name = 'timeseries.Input'
    assert model.recorders['timeseries.Input'] == rec
    with pytest.raises(KeyError):
        model.recorders['flowdurationcurverecorder.catchment1']

    model.run()

    assert_allclose(rec.fdc[:, 0], [20.42,  21.78,  23.22,  26.47,  29.31])
    assert_allclose(np.max(rec.fdc, axis=0), rec.values())
    assert_allclose(np.min(np.max(rec.fdc, axis=0)), rec.aggregated_value())

    assert rec.fdc.shape == (len(percentiles), len(model.scenarios.combinations))
    df = rec.to_dataframe()
    assert df.shape == (len(percentiles), len(model.scenarios.combinations))

def test_fdc_dev_recorder():
    """
    Test the FlowDurationCurveDeviationRecorder
    """
    model = load_model("timeseries2.json")
    input = model.nodes['catchment1']
    scenarioA = model.scenarios['scenario A']

    natural_flow = pandas.read_csv(os.path.join(os.path.dirname(__file__), 'models', 'timeseries2.csv'),
                                   parse_dates=True, dayfirst=True, index_col=0)

    percentiles = np.linspace(20., 100., 5)

    natural_fdc = np.percentile(natural_flow, percentiles, axis=0)

    # Lower target is 20% below natural
    lower_input_fdc = natural_fdc * 0.8
    # Upper is 10% above
    upper_input_fdc = natural_fdc * 1.1

    rec = FlowDurationCurveDeviationRecorder(model, input, percentiles, lower_input_fdc, upper_input_fdc,
                                             fdc_agg_func="min",
                                             agg_func="mean", scenario=scenarioA)

    # test retrieval of recorder
    assert model.recorders['flowdurationcurvedeviationrecorder.catchment1'] == rec
    # test changing name of recorder
    rec.name = 'timeseries.Input'
    assert model.recorders['timeseries.Input'] == rec
    with pytest.raises(KeyError):
        model.recorders['flowdurationcurvedeviationrecorder.catchment1']

    model.run()

    # Compute deviation
    lower_deviation = (lower_input_fdc - natural_fdc) / lower_input_fdc
    upper_deviation = (natural_fdc - upper_input_fdc) / upper_input_fdc
    deviation = np.maximum(np.maximum(lower_deviation, upper_deviation), np.zeros_like(lower_deviation))
    print(deviation, lower_deviation, upper_deviation)

    assert_allclose(rec.fdc_deviations[:, 0], deviation[:, 0])
    assert_allclose(np.min(rec.fdc_deviations, axis=0), rec.values())
    assert_allclose(np.mean(np.min(rec.fdc_deviations, axis=0)), rec.aggregated_value())

    assert rec.fdc_deviations.shape == (len(percentiles), len(model.scenarios.combinations))
    df = rec.to_dataframe()
    assert df.shape == (len(percentiles), len(model.scenarios.combinations))

def test_numpy_storage_recorder(simple_storage_model):
    """
    Test the NumpyArrayStorageRecorder
    """
    model = simple_storage_model

    res = model.nodes['Storage']

    rec = NumpyArrayStorageRecorder(model, res)

    model.run()

    assert(rec.data.shape == (5, 1))
    assert_allclose(rec.data, np.array([[7, 4, 1, 0, 0]]).T, atol=1e-7)


    df = rec.to_dataframe()
    assert df.shape == (5, 1)
    assert_allclose(df.values, np.array([[7, 4, 1, 0, 0]]).T, atol=1e-7)


def test_numpy_parameter_recorder(simple_linear_model):
    """
    Test the NumpyArrayParameterRecorder
    """
    from pywr.parameters import DailyProfileParameter

    model = simple_linear_model
    # using leap year simplifies tests
    model.timestepper.start = pandas.to_datetime("2016-01-01")
    model.timestepper.end = pandas.to_datetime("2016-12-31")
    otpt = model.nodes['Output']

    p = DailyProfileParameter(model, np.arange(366, dtype=np.float64), )
    p.name = 'daily profile'
    model.nodes['Input'].max_flow = p
    otpt.cost = -2.0
    rec = NumpyArrayParameterRecorder(model, model.nodes['Input'].max_flow)

    # test retrieval of recorder
    assert model.recorders['numpyarrayparameterrecorder.daily profile'] == rec

    model.run()

    assert rec.data.shape == (366, 1)
    assert_allclose(rec.data, np.arange(366, dtype=np.float64)[:, np.newaxis])

    df = rec.to_dataframe()
    assert df.shape == (366, 1)
    assert_allclose(df.values, np.arange(366, dtype=np.float64)[:, np.newaxis])


def test_numpy_index_parameter_recorder(simple_storage_model):
    """
    Test the NumpyArrayIndexParameterRecorder

    Note the parameter is recorded at the start of the timestep, while the
    storage is recorded at the end of the timestep.
    """
    from pywr.parameters.control_curves import ControlCurveIndexParameter

    model = simple_storage_model

    res = model.nodes['Storage']

    p = ControlCurveIndexParameter(model, res, [5.0/20.0, 2.5/20.0])

    res_rec = NumpyArrayStorageRecorder(model, res)
    lvl_rec = NumpyArrayIndexParameterRecorder(model, p)

    model.run()

    assert(res_rec.data.shape == (5, 1))
    assert_allclose(res_rec.data, np.array([[7, 4, 1, 0, 0]]).T, atol=1e-7)
    assert (lvl_rec.data.shape == (5, 1))
    assert_allclose(lvl_rec.data, np.array([[0, 0, 1, 2, 2]]).T, atol=1e-7)


    df = lvl_rec.to_dataframe()
    assert df.shape == (5, 1)
    assert_allclose(df.values, np.array([[0, 0, 1, 2, 2]]).T, atol=1e-7)


def test_parameter_recorder_json(solver):
    model = load_model("parameter_recorder.json", solver=solver)
    rec_demand = model.recorders["demand_max_recorder"]
    rec_supply = model.recorders["supply_max_recorder"]
    model.run()
    assert_allclose(rec_demand.data, 10)
    assert_allclose(rec_supply.data, 15)


def test_parameter_mean_recorder(simple_linear_model):
    model = simple_linear_model
    # using leap year simplifies test
    model.timestepper.start = pandas.to_datetime("2016-01-01")
    model.timestepper.end = pandas.to_datetime("2016-12-31")

    node = model.nodes["Input"]
    values = np.arange(0, 366, dtype=np.float64)
    node.max_flow = DailyProfileParameter(model, values)

    scenario = Scenario(model, "dummy", size=3)

    timesteps = 3
    rec_mean = RollingWindowParameterRecorder(model, node.max_flow, timesteps, "mean", name="rec_mean")
    rec_sum = RollingWindowParameterRecorder(model, node.max_flow, timesteps, "sum", name="rec_sum")
    rec_min = RollingWindowParameterRecorder(model, node.max_flow, timesteps, "min", name="rec_min")
    rec_max = RollingWindowParameterRecorder(model, node.max_flow, timesteps, "max", name="rec_max")

    model.run()

    assert_allclose(rec_mean.data[[0, 1, 2, 3, 364], 0], [0, 0.5, 1, 2, 363])
    assert_allclose(rec_max.data[[0, 1, 2, 3, 364], 0], [0, 1, 2, 3, 364])
    assert_allclose(rec_min.data[[0, 1, 2, 3, 364], 0], [0, 0, 0, 1, 362])
    assert_allclose(rec_sum.data[[0, 1, 2, 3, 364], 0], [0, 1, 3, 6, 1089])

def test_parameter_mean_recorder_json(simple_linear_model):
    model = simple_linear_model
    node = model.nodes["Input"]
    values = np.arange(0, 366, dtype=np.float64)
    parameter = DailyProfileParameter(model, values, name="input_max_flow")

    node.max_flow = parameter

    data = {
        "type": "rollingwindowparameter",
        "parameter": "input_max_flow",
        "window": 3,
        "agg_func": "mean",
    }

    rec = load_recorder(model, data)


def test_concatenated_dataframes(simple_storage_model):
    """
    Test that Model.to_dataframe returns something sensible.

    """
    model = simple_storage_model

    scA = Scenario(model, 'A', size=2)
    scB = Scenario(model, 'B', size=3)

    res = model.nodes['Storage']
    rec1 = NumpyArrayStorageRecorder(model, res)
    otpt = model.nodes['Output']
    rec2 = NumpyArrayNodeRecorder(model, otpt)
    # The following can't return a DataFrame; is included to check
    # it doesn't cause any issues
    rec3 = TotalDeficitNodeRecorder(model, otpt)

    model.run()

    df = model.to_dataframe()
    assert df.shape == (5, 2*2*3)
    assert df.columns.names == ['Recorder', 'A', 'B']


def test_csv_recorder(simple_linear_model, tmpdir):
    """
    Test the CSV Recorder

    """
    model = simple_linear_model
    otpt = model.nodes['Output']
    model.nodes['Input'].max_flow = 10.0
    otpt.cost = -2.0

    csvfile = tmpdir.join('output.csv')
    # By default the CSVRecorder saves all nodes in alphabetical order
    # and scenario index 0.
    rec = CSVRecorder(model, str(csvfile))

    model.run()

    import csv
    with open(str(csvfile), 'r') as fh:
        dialect = csv.Sniffer().sniff(fh.read(1024))
        fh.seek(0)
        reader = csv.reader(fh, dialect)
        for irow, row in enumerate(reader):
            if irow == 0:
                expected = ['Datetime', 'Input', 'Link', 'Output']
                actual = row
            else:
                dt = model.timestepper.start+(irow-1)*model.timestepper.delta
                expected = [dt.isoformat()]
                actual = [row[0]]
                assert np.all((np.array([float(v) for v in row[1:]]) - 10.0) < 1e-12)
            assert expected == actual


class TestTablesRecorder:

    def test_create_directory(self, simple_linear_model, tmpdir):
        """ Test TablesRecorder to create a new directory """

        model = simple_linear_model
        otpt = model.nodes['Output']
        inpt = model.nodes['Input']
        agg_node = AggregatedNode(model, 'Sum', [otpt, inpt])

        inpt.max_flow = 10.0
        otpt.cost = -2.0
        # Make a path with a new directory
        folder = tmpdir.join('outputs')
        h5file = folder.join('output.h5')
        assert(not folder.exists())
        rec = TablesRecorder(model, str(h5file), create_directories=True)
        model.run()
        assert(folder.exists())
        assert(h5file.exists())

    def test_nodes(self, simple_linear_model, tmpdir):
        """
        Test the TablesRecorder

        """
        model = simple_linear_model
        otpt = model.nodes['Output']
        inpt = model.nodes['Input']
        agg_node = AggregatedNode(model, 'Sum', [otpt, inpt])

        inpt.max_flow = 10.0
        otpt.cost = -2.0

        h5file = tmpdir.join('output.h5')
        import tables
        with tables.open_file(str(h5file), 'w') as h5f:
            rec = TablesRecorder(model, h5f)

            model.run()

            for node_name in model.nodes.keys():
                ca = h5f.get_node('/', node_name)
                assert ca.shape == (365, 1)
                if node_name == 'Sum':
                    np.testing.assert_allclose(ca, 20.0)
                else:
                    np.testing.assert_allclose(ca, 10.0)

            from datetime import date, timedelta
            d = date(2015, 1, 1)
            time = h5f.get_node('/time')
            for i in range(len(model.timestepper)):
                row = time[i]
                assert row['year'] == d.year
                assert row['month'] == d.month
                assert row['day'] == d.day

                d += timedelta(1)

            scenarios = h5f.get_node('/scenarios')
            for s in model.scenarios.scenarios:
                row = scenarios[i]
                assert row['name'] == s.name
                assert row['size'] == s.size

            model.reset()
            model.run()

            time = h5f.get_node('/time')
            assert len(time) == len(model.timestepper)

    def test_multiple_scenarios(self, simple_linear_model, tmpdir):
        """
        Test the TablesRecorder

        """
        from pywr.parameters import ConstantScenarioParameter
        model = simple_linear_model
        scA = Scenario(model, name='A', size=4)
        scB = Scenario(model, name='B', size=2)

        otpt = model.nodes['Output']
        inpt = model.nodes['Input']

        inpt.max_flow = ConstantScenarioParameter(model, scA, [10, 20, 30, 40])
        otpt.max_flow = ConstantScenarioParameter(model, scB, [20, 40])
        otpt.cost = -2.0

        h5file = tmpdir.join('output.h5')
        import tables
        with tables.open_file(str(h5file), 'w') as h5f:
            rec = TablesRecorder(model, h5f)

            model.run()

            for node_name in model.nodes.keys():
                ca = h5f.get_node('/', node_name)
                assert ca.shape == (365, 4, 2)
                np.testing.assert_allclose(ca[0, ...], [[10, 10], [20, 20], [20, 30], [20, 40]])

    def test_parameters(self, simple_linear_model, tmpdir):
        """
        Test the TablesRecorder

        """
        from pywr.parameters import ConstantParameter

        model = simple_linear_model
        otpt = model.nodes['Output']
        inpt = model.nodes['Input']

        p = ConstantParameter(model, 10.0, name='max_flow')
        inpt.max_flow = p

        # ensure TablesRecorder can handle parameters with a / in the name
        p_slash = ConstantParameter(model, 0.0, name='name with a / in it')
        inpt.min_flow = p_slash

        agg_node = AggregatedNode(model, 'Sum', [otpt, inpt])

        inpt.max_flow = 10.0
        otpt.cost = -2.0

        h5file = tmpdir.join('output.h5')
        import tables
        with tables.open_file(str(h5file), 'w') as h5f:
            rec = TablesRecorder(model, h5f, parameters=[p, p_slash])

            # check parameters have been added to the component tree
            # this is particularly important for parameters which update their
            # values in `after`, e.g. DeficitParameter (see #465)
            assert(not model.find_orphaned_parameters())
            assert(p in rec.children)
            assert(p_slash in rec.children)

            model.run()

            for node_name in model.nodes.keys():
                ca = h5f.get_node('/', node_name)
                assert ca.shape == (365, 1)
                if node_name == 'Sum':
                    np.testing.assert_allclose(ca, 20.0)
                elif "name with a" in node_name:
                    assert(node_name == "name with a _ in it")
                    np.testing.assert_allclose(ca, 0.0)
                else:
                    np.testing.assert_allclose(ca, 10.0)

    def test_nodes_with_str(self, simple_linear_model, tmpdir):
        """
        Test the TablesRecorder

        """
        from pywr.parameters import ConstantParameter

        model = simple_linear_model
        otpt = model.nodes['Output']
        inpt = model.nodes['Input']
        agg_node = AggregatedNode(model, 'Sum', [otpt, inpt])
        p = ConstantParameter(model, 10.0, name='max_flow')
        inpt.max_flow = p

        otpt.cost = -2.0

        h5file = tmpdir.join('output.h5')
        import tables
        with tables.open_file(str(h5file), 'w') as h5f:
            nodes = ['Output', 'Input', 'Sum']
            where = "/agroup"
            rec = TablesRecorder(model, h5f, nodes=nodes,
                                 parameters=[p, ], where=where)

            model.run()

            for node_name in ['Output', 'Input', 'Sum', 'max_flow']:
                ca = h5f.get_node("/agroup/" + node_name)
                assert ca.shape == (365, 1)
                if node_name == 'Sum':
                    np.testing.assert_allclose(ca, 20.0)
                else:
                    np.testing.assert_allclose(ca, 10.0)

    def test_demand_saving_with_indexed_array(self, solver, tmpdir):
        """Test recording various items from demand saving example

        """
        model = load_model("demand_saving2.json", solver=solver)

        model.timestepper.end = "2016-01-31"

        model.check()

        h5file = tmpdir.join('output.h5')
        import tables
        with tables.open_file(str(h5file), 'w') as h5f:

            nodes = [
                ('/outputs/demand', 'Demand'),
                ('/storage/reservoir', 'Reservoir'),
            ]

            parameters = [
                ('/parameters/demand_saving_level', 'demand_saving_level'),
            ]

            rec = TablesRecorder(model, h5f, nodes=nodes, parameters=parameters)

            model.run()

            max_volume = model.nodes["Reservoir"].max_volume
            rec_demand = h5f.get_node('/outputs/demand', 'Demand').read()
            rec_storage = h5f.get_node('/storage/reservoir', 'Reservoir').read()

            # model starts with no demand saving
            demand_baseline = 50.0
            demand_factor = 0.9  # jan-apr
            demand_saving = 1.0
            assert_allclose(rec_demand[0, 0], demand_baseline * demand_factor * demand_saving)

            # first control curve breached
            demand_saving = 0.95
            assert (rec_storage[4, 0] < (0.8 * max_volume))
            assert_allclose(rec_demand[5, 0], demand_baseline * demand_factor * demand_saving)

            # second control curve breached
            demand_saving = 0.5
            assert (rec_storage[11, 0] < (0.5 * max_volume))
            assert_allclose(rec_demand[12, 0], demand_baseline * demand_factor * demand_saving)

    def test_demand_saving_with_indexed_array(self, solver, tmpdir):
        """Test recording various items from demand saving example.

        This time the TablesRecorder is defined in JSON.
        """
        import os, json, tables
        filename = "demand_saving_with_tables_recorder.json"
        # This is a bit horrible, but need to edit the JSON dynamically
        # so that the output.h5 is written in the temporary directory
        path = os.path.join(os.path.dirname(__file__), 'models')
        with open(os.path.join(path, filename), 'r') as f:
            data = f.read()
        data = json.loads(data)

        # Make an absolute, but temporary, path for the recorder
        url = data['recorders']['database']['url']
        data['recorders']['database']['url'] = str(tmpdir.join(url))

        model = Model.load(data, path=path, solver=solver)

        model.timestepper.end = "2016-01-31"
        model.check()

        # run model
        model.run()

        # run model again (to test reset behaviour)
        model.run()
        max_volume = model.nodes["Reservoir"].max_volume

        h5file = tmpdir.join('output.h5')
        with tables.open_file(str(h5file), 'r') as h5f:
            assert model.metadata['title'] == h5f.title
            # Check metadata on root node
            assert h5f.root._v_attrs.author == 'pytest'
            assert h5f.root._v_attrs.run_number == 0

            rec_demand = h5f.get_node('/outputs/demand').read()
            rec_storage = h5f.get_node('/storage/reservoir').read()

            # model starts with no demand saving
            demand_baseline = 50.0
            demand_factor = 0.9  # jan-apr
            demand_saving = 1.0
            assert_allclose(rec_demand[0, 0], demand_baseline * demand_factor * demand_saving)

            # first control curve breached
            demand_saving = 0.95
            assert (rec_storage[4, 0] < (0.8 * max_volume))
            assert_allclose(rec_demand[5, 0], demand_baseline * demand_factor * demand_saving)

            # second control curve breached
            demand_saving = 0.5
            assert (rec_storage[11, 0] < (0.5 * max_volume))
            assert_allclose(rec_demand[12, 0], demand_baseline * demand_factor * demand_saving)


def test_total_deficit_node_recorder(simple_linear_model):
    """
    Test TotalDeficitNodeRecorder
    """
    model = simple_linear_model
    model.timestepper.delta = 5
    otpt = model.nodes['Output']
    otpt.max_flow = 30.0
    model.nodes['Input'].max_flow = 10.0
    otpt.cost = -2.0
    rec = TotalDeficitNodeRecorder(model, otpt)

    model.step()
    assert_allclose(20.0*5, rec.aggregated_value(), atol=1e-7)

    model.step()
    assert_allclose(40.0*5, rec.aggregated_value(), atol=1e-7)


def test_total_flow_node_recorder(simple_linear_model):
    """
    Test TotalDeficitNodeRecorder
    """
    model = simple_linear_model
    otpt = model.nodes['Output']
    otpt.max_flow = 30.0
    model.nodes['Input'].max_flow = 10.0
    otpt.cost = -2.0
    rec = TotalFlowNodeRecorder(model, otpt)

    model.step()
    assert_allclose(10.0, rec.aggregated_value(), atol=1e-7)

    model.step()
    assert_allclose(20.0, rec.aggregated_value(), atol=1e-7)


class TestAggregatedParameter:
    """Tests for AggregatedParameter"""
    funcs = {"min": np.min, "max": np.max, "mean": np.mean, "sum": np.sum}

    @pytest.mark.parametrize("agg_func", ["min", "max", "mean", "sum"])
    def test_aggregated_recorder(self, simple_linear_model, agg_func):
        model = simple_linear_model
        otpt = model.nodes['Output']
        otpt.max_flow = 30.0
        model.nodes['Input'].max_flow = 10.0
        otpt.cost = -2.0
        rec1 = TotalFlowNodeRecorder(model, otpt)
        rec2 = TotalDeficitNodeRecorder(model, otpt)

        func = TestAggregatedParameter.funcs[agg_func]

        rec = AggregatedRecorder(model, [rec1, rec2], agg_func=agg_func)

        model.step()
        assert_allclose(func([10.0, 20.0]), rec.aggregated_value(), atol=1e-7)

        model.step()
        assert_allclose(func([20.0, 40.0]), rec.aggregated_value(), atol=1e-7)


def test_reset_timestepper_recorder(solver):
    model = Model(
        solver=solver,
        start=pandas.to_datetime('2016-01-01'),
        end=pandas.to_datetime('2016-01-01')
    )

    inpt = Input(model, "input", max_flow=10)
    otpt = Output(model, "output", max_flow=50, cost=-10)
    inpt.connect(otpt)

    rec = NumpyArrayNodeRecorder(model, otpt)

    model.run()

    model.timestepper.end = pandas.to_datetime("2016-01-02")

    model.run()

def test_mean_flow_recorder(solver):
    model = Model(solver=solver)
    model.timestepper.start = pandas.to_datetime("2016-01-01")
    model.timestepper.end = pandas.to_datetime("2016-01-04")

    inpt = Input(model, "input")
    otpt = Output(model, "output")
    inpt.connect(otpt)

    rec_flow = NumpyArrayNodeRecorder(model, inpt)
    rec_mean = MeanFlowRecorder(model, node=inpt, timesteps=3)

    scenario = Scenario(model, "dummy", size=2)

    inpt.max_flow = inpt.min_flow = FunctionParameter(model, inpt, lambda model, t, si: 2 + t.index)
    model.run()

    expected = [
        2.0,
        (2.0 + 3.0) / 2,
        (2.0 + 3.0 + 4.0) / 3,
        (3.0 + 4.0 + 5.0) / 3,  # zeroth day forgotten
    ]

    for value, expected_value in zip(rec_mean.data[:, 0], expected):
        assert_allclose(value, expected_value)

def test_mean_flow_recorder_days(solver):
    model = Model(solver=solver)
    model.timestepper.delta = 7

    inpt = Input(model, "input")
    otpt = Output(model, "output")
    inpt.connect(otpt)

    rec_mean = MeanFlowRecorder(model, node=inpt, days=31)

    model.run()
    assert(rec_mean.timesteps == 4)

def test_mean_flow_recorder_json(solver):
    model = load_model("mean_flow_recorder.json", solver=solver)

    # TODO: it's not possible to define a FunctionParameter in JSON yet
    supply1 = model.nodes["supply1"]
    supply1.max_flow = supply1.min_flow = FunctionParameter(model, supply1, lambda model, t, si: 2 + t.index)

    assert(len(model.recorders) == 3)

    rec_flow = model.recorders["Supply"]
    rec_mean = model.recorders["Mean Flow"]
    rec_check = model.recorders["Supply 2"]

    model.run()

    assert_allclose(rec_flow.data[:,0], [2.0, 3.0, 4.0, 5.0])
    assert_allclose(rec_mean.data[:,0], [2.0, 2.5, 3.0, 4.0])
    assert_allclose(rec_check.data[:,0], [50.0, 50.0, 60.0, 60.0])

def test_annual_count_index_parameter_recorder(simple_storage_model):
    """ Test AnnualCountIndexParameterRecord

    The test sets uses a simple reservoir model with different inputs that
    trigger a control curve failure after different numbers of years.
    """
    from pywr.parameters import ConstantScenarioParameter, ConstantParameter
    from pywr.parameters.control_curves import ControlCurveIndexParameter
    model = simple_storage_model
    scenario = Scenario(model, 'A', size=2)
    # Simulate 5 years
    model.timestepper.start = '2015-01-01'
    model.timestepper.end = '2019-12-31'
    # Control curve parameter
    param = ControlCurveIndexParameter(model, model.nodes['Storage'], ConstantParameter(model, 0.25))

    # Storage model has a capacity of 20, but starts at 10 Ml
    # Demand is roughly 2 Ml/d per year
    #  First ensemble balances the demand
    #  Second ensemble should fail during 3rd year
    demand = 2.0 / 365
    model.nodes['Input'].max_flow = ConstantScenarioParameter(model, scenario, [demand, 0])
    model.nodes['Output'].max_flow = demand

    # Create the recorder with a threshold of 1
    rec = AnnualCountIndexParameterRecorder(model, param, 1)

    model.run()
    # We expect no failures in the first ensemble, but 3 out of 5 in the second
    assert_allclose(rec.values(), [0, 3])


# The following fixtures are used for testing the recorders in
#  pywr.recorders.calibration which require an observed data set
#  to compare with the model prediction.

@pytest.fixture
def timeseries2_model(solver):
    return load_model('timeseries2.json', solver=solver)


@pytest.fixture
def timeseries2_observed():
    path = os.path.join(os.path.dirname(__file__), 'models')
    df = pandas.read_csv(os.path.join(path, 'timeseries2.csv'),
                         parse_dates=True, dayfirst=True, index_col=0)
    df = df.asfreq(pandas.infer_freq(df.index))
    # perturb a bit
    df += np.random.normal(size=df.shape)
    return df

class TestCalibrationRecorders:
    data = [
        (RootMeanSquaredErrorNodeRecorder, lambda sim, obs: np.sqrt(np.mean((sim-obs)**2, axis=0))),
        (MeanAbsoluteErrorNodeRecorder, lambda sim, obs: np.mean(np.abs(sim-obs), axis=0)),
        (MeanSquareErrorNodeRecorder, lambda sim, obs: np.mean((sim-obs)**2, axis=0)),
        (PercentBiasNodeRecorder, lambda sim, obs: np.sum(obs-sim, axis=0)*100/np.sum(obs, axis=0)),
        (RMSEStandardDeviationRatioNodeRecorder, lambda sim, obs: np.sqrt(np.mean((obs-sim)**2, axis=0))/np.std(obs, axis=0)),
        (NashSutcliffeEfficiencyNodeRecorder, lambda sim, obs: 1.0 - np.sum((obs-sim)**2, axis=0)/np.sum((obs-obs.mean())**2, axis=0)),
    ]
    ids = ["rmse", "mae", "mse", "pbias", "rmse", "ns"]

    @pytest.mark.parametrize("cls,func", data, ids=ids)
    def test_calibration_recorder(self, timeseries2_model, timeseries2_observed, cls, func):
        model = timeseries2_model
        observed = timeseries2_observed
        node = model.nodes["river1"]
        recorder = cls(model, node, observed)

        model.run()

        simulated = model.nodes["catchment1"].max_flow.dataframe
        metric = func(simulated, observed)
        values = recorder.values()
        assert(values.shape[0] == len(model.scenarios.combinations))
        assert(values.ndim == 1)
        assert_allclose(metric, values)


@pytest.fixture
def cyclical_storage_model(simple_storage_model):
    """ Extends simple_storage_model to have a cyclical boundary condition """
    from pywr.parameters import AnnualHarmonicSeriesParameter, ConstantScenarioParameter
    m = simple_storage_model
    s = Scenario(m, name='Scenario A', size=3)

    m.timestepper.end = '2017-12-31'
    m.timestepper.delta = 5

    inpt = m.nodes['Input']
    inpt.max_flow = AnnualHarmonicSeriesParameter(m, 5, [0.1, 0.0, 0.25], [0.0, 0.0, 0.0])

    otpt = m.nodes['Output']
    otpt.max_flow = ConstantScenarioParameter(m, s, [5, 6, 2])

    return m


@pytest.fixture
def cyclical_linear_model(simple_linear_model):
    """ Extends simple_storage_model to have a cyclical boundary condition """
    from pywr.parameters import AnnualHarmonicSeriesParameter, ConstantScenarioParameter
    m = simple_linear_model
    s = Scenario(m, name='Scenario A', size=3)

    m.timestepper.end = '2017-12-31'
    m.timestepper.delta = 5

    inpt = m.nodes['Input']
    inpt.max_flow = AnnualHarmonicSeriesParameter(m, 5, [1.0, 0.0, 0.5], [0.0, 0.0, 0.0])

    otpt = m.nodes['Output']
    otpt.max_flow = ConstantScenarioParameter(m, s, [5, 6, 2])
    otpt.cost = -10.0

    return m


class TestEventRecorder:
    """ Tests for EventRecorder """
    funcs = {"min": np.min, "max": np.max, "mean": np.mean, "median": np.median, "sum": np.sum}

    @pytest.mark.parametrize("recorder_agg_func", ["min", "max", "mean", "median", "sum"])
    def test_event_capture_with_storage(self, cyclical_storage_model, recorder_agg_func):
        """ Test Storage events using a StorageThresholdRecorder """
        m = cyclical_storage_model

        strg = m.nodes['Storage']
        arry = NumpyArrayStorageRecorder(m, strg)

        # Create the trigger using a threhsold parameter
        trigger = StorageThresholdRecorder(m, strg, 4.0, predicate='<=')
        evt_rec = EventRecorder(m, trigger)
        evt_dur = EventDurationRecorder(m, evt_rec, recorder_agg_func=recorder_agg_func, agg_func='max')

        m.run()

        # Ensure there is at least one event
        assert evt_rec.events

        # Build a timeseries of when the events say an event is active
        triggered = np.zeros_like(arry.data, dtype=np.int)
        for evt in evt_rec.events:
            triggered[evt.start.index:evt.end.index, evt.scenario_index.global_id] = 1

            # Check the duration
            td = evt.end.datetime - evt.start.datetime
            assert evt.duration == td.days

        # Test that the volumes in the Storage node during the event periods match
        assert_equal(triggered, arry.data <= 4)

        df = evt_rec.to_dataframe()

        assert len(df) == len(evt_rec.events)

        func = TestEventRecorder.funcs[recorder_agg_func]

        # Now check the EventDurationRecorder does the aggregation correctly
        expected_durations = []
        for si in m.scenarios.combinations:
            event_durations = []
            for evt in evt_rec.events:
                if evt.scenario_index.global_id == si.global_id:
                    event_durations.append(evt.duration)

            # If there are no events then the metric is zero
            if len(event_durations) > 0:
                expected_durations.append(func(event_durations))
            else:
                expected_durations.append(0.0)

        assert_allclose(evt_dur.values(), expected_durations)
        assert_allclose(evt_dur.aggregated_value(), np.max(expected_durations))

    def test_event_capture_with_node(self, cyclical_linear_model):
        """ Test Node flow events using a NodeThresholdRecorder """
        m = cyclical_linear_model

        otpt = m.nodes['Output']
        arry = NumpyArrayNodeRecorder(m, otpt)

        # Create the trigger using a threhsold parameter
        trigger = NodeThresholdRecorder(m, otpt, 4.0, predicate='>')
        evt_rec = EventRecorder(m, trigger)

        m.run()

        # Ensure there is at least one event
        assert evt_rec.events

        # Build a timeseries of when the events say an event is active
        triggered = np.zeros_like(arry.data, dtype=np.int)
        for evt in evt_rec.events:
            triggered[evt.start.index:evt.end.index, evt.scenario_index.global_id] = 1

            # Check the duration
            td = evt.end.datetime - evt.start.datetime
            assert evt.duration == td.days

        # Test that the volumes in the Storage node during the event periods match
        assert_equal(triggered, arry.data > 4)

    @pytest.mark.parametrize("recorder_agg_func", ["min", "max", "mean", "median", "sum"])
    def test_no_event_capture_with_storage(self, cyclical_storage_model, recorder_agg_func):
        """ Test Storage events using a StorageThresholdRecorder """
        m = cyclical_storage_model

        strg = m.nodes['Storage']
        arry = NumpyArrayStorageRecorder(m, strg)

        # Create the trigger using a threhsold parameter
        trigger = StorageThresholdRecorder(m, strg, -1.0, predicate='<')
        evt_rec = EventRecorder(m, trigger)
        evt_dur = EventDurationRecorder(m, evt_rec, recorder_agg_func=recorder_agg_func, agg_func='max')

        m.run()

        # Ensure there are no events in this test
        assert len(evt_rec.events) == 0
        df = evt_rec.to_dataframe()
        assert len(df) == 0

        assert_allclose(evt_dur.values(), np.zeros(len(m.scenarios.combinations)))
        assert_allclose(evt_dur.aggregated_value(), 0)

    @pytest.mark.parametrize("minimum_length", [1, 2, 3, 4])
    def test_hysteresis(self, simple_linear_model, minimum_length):
        """ Test the minimum_event_length keyword of EventRecorder """
        m = simple_linear_model

        flow = np.zeros(len(m.timestepper))

        flow[:10] = [0, 0, 10, 0, 10, 10, 10, 0, 0, 0]
        # With min event length of 1. There are two events with lengths (1, 3)
        #                 |---|   |---------|
        # With min event length up to 4. There is one event with length 3
        #                         |---------|
        # Min event length >= 4 gives no events

        inpt = m.nodes['Input']
        inpt.max_flow = ArrayIndexedParameter(m, flow)

        # Force through whatever flow Input can provide
        otpt = m.nodes['Output']
        otpt.max_flow = 100
        otpt.cost = -100

        # Create the trigger using a threhsold parameter
        trigger = NodeThresholdRecorder(m, otpt, 4.0, predicate='>')
        evt_rec = EventRecorder(m, trigger, minimum_event_length=minimum_length)

        m.run()

        if minimum_length == 1:
            assert len(evt_rec.events) == 2
            assert_equal([1, 3], [e.duration for e in evt_rec.events])
        elif minimum_length < 4:
            assert len(evt_rec.events) == 1
            assert_equal([3, ], [e.duration for e in evt_rec.events])
        else:
            assert len(evt_rec.events) == 0
