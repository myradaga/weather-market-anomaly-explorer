import pytest
from app.normalize.fills import signed_yes_exposure
@pytest.mark.parametrize("side,outcome,expected",[("BUY","YES",10),("SELL","YES",-10),("BUY","NO",-10),("SELL","NO",10)])
def test_signed_exposure(side,outcome,expected): assert signed_yes_exposure(side,outcome,10,1)==expected

