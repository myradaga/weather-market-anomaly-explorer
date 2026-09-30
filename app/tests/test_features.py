import numpy as np
from app.features.size import robust_z,percentile
from app.features.timing import signed_return
from app.features.order_flow import order_imbalance
from app.features.profitability import profitability_test,bh_qvalues
def test_features():
    assert percentile(2,[1,2,3])==2/3
    assert robust_z([1,2,100])[-1]>1
    assert signed_return(.4,.6,"YES")>0 and signed_return(.4,.6,"NO")<0
    assert order_imbalance([10,-2],[10,2])==pytest.approx(2/3)
    assert profitability_test([.5]*10,[1]*10)["profit_z"]>0
    assert np.all(bh_qvalues([.01,.2])<=1)
import pytest

