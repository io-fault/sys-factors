"""
Metrics validation.
"""
from ..xml import libmetrics

valids = {
	'simple':
		"""
			<report timestamp="2001-01-01T03:15:01.000001"
				xmlns:key="https://fault.io/xml/key"
				xmlns="https://fault.io/xml/metrics#profile">
				<measurements xml:id="floor" dimensions="field3.cat.name field2 field" fields="attribute names of measures">
					<frame key:field2="value" total="" average=""/>
				</measurements>
			</report>
		""",

	'empty-elements-no-xml-ids':
		"""
			<report timestamp="2001-01-01T02:30:00"
				xmlns:key="https://fault.io/xml/key"
				xmlns="https://fault.io/xml/metrics#profile">
				<measurements><frame/></measurements>
			</report>
		""",
}

invalids = {
	'bad-timestamp':
		"""
			<report timestamp="Fail."
				xmlns:key="https://fault.io/xml/key"
				xmlns="https://fault.io/xml/metrics#profile">

				<measurements xml:id="floor" dimensions="field3.cat.name field2 field" fields="attribute names of measures">
					<frame key:field2="value" total="" average=""/>
				</measurements>
			</report>
		""",

	'bad-dimension-name':
		"""
			<report timestamp="2001-01-01T02:30:00"
				xmlns:key="https://fault.io/xml/key"
				xmlns="https://fault.io/xml/metrics#profile">

				<measurements xml:id="floor" dimensions="?? ?? ??" fields="attribute names of measures">
					<frame key:field2="value" total="" average=""/>
				</measurements>
			</report>
		""",

	'bad-field-name':
		"""
			<report timestamp="2001-01-01T02:30:00"
				xmlns:key="https://fault.io/xml/key"
				xmlns="https://fault.io/xml/metrics#profile">

				<measurements xml:id="floor" dimensions="Correct" fields="!! !! !!">
					<frame key:field2="value" total="" average=""/>
				</measurements>
			</report>
		""",

	'invalid-element':
		"""
			<report timestamp="2001-01-01T02:30:00"
				xmlns:key="https://fault.io/xml/key"
				xmlns="https://fault.io/xml/metrics#profile">

				<bad.element/>
			</report>
		""",
}

def test_valids(test):
	for label, x in valids.items():
		x = libmetrics.etree.XML(x)
		test/libmetrics.valid(x) == True

def test_invalids(test):
	for label, x in invalids.items():
		x = libmetrics.etree.XML(x)
		test/libmetrics.valid(x) == False
