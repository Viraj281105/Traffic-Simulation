"""What a valid configuration is: V1.4 scenario documents (parse, validate per
strategy, compile to an engine configuration) and the cross-field and lane
rules the JSON schema cannot express.

Sits above controllers in the domain (it reads their tuning bounds) and is
imported by the application and delivery layers, never by the engine.
"""
