import numpy as np
import features

def transform(data_x):
    return np.hstack([
        features.expand_to_adjacent(data_x, width=1),
        features.rolling_aggregates(data_x, width=2, aggregate=np.max),
        features.rolling_aggregates(data_x, width=5, aggregate=np.max)
    ])

def normalize(data_x):
    #from sklearn.preprocessing import StandardScaler
    #return StandardScaler().fit_transform(data_x)
    #return data_x - np.mean(data_x, axis=0)
    return data_x


def find_sync_bias(speech_detection, training_x, training_y, training_meta, verbose=False):
    import find_transform
    shifts = []
    accs = []

    if verbose:
        print('finding sync bias')

    for file_number in np.unique(training_meta.file_number):
        part = training_meta.file_number == file_number
        y = training_y[part]
        predicted_score = predict([speech_detection, None], training_x[part, :], y)
        shift = find_transform.find_transform_parameters(y, predicted_score, fixed_skew=1.0)[1]
        acc = np.mean(np.round(predicted_score) == y)
        shifts.append(shift)
        accs.append([acc, len(y)])

        if verbose:
            print(shift)

    accs = np.array(accs)
    acc = np.sum(accs[:,0]*accs[:,1])/np.sum(accs[:,1])
    bias = -np.round(np.mean(shifts) / features.frame_secs) * features.frame_secs

    if verbose:
        print('training accuracy', acc)
        print('bias %g s' % bias)

    return bias

def train(training_x, training_y, training_meta, verbose=False):
    from sklearn.linear_model import LogisticRegression as classifier
    #from sklearn.ensemble import GradientBoostingClassifier as classifier

    file_labels = training_meta.file_number.values

    training_weights = features.weight_by_group_and_file(training_meta.language, file_labels)
    #print(np.unique(training_weights))
    training_x_normalized = features.normalize_by_file(training_x, normalize, file_labels)
    training_x_normalized = transform(training_x_normalized)

    speech_detection = classifier(penalty='l1', C=0.001)
    speech_detection.fit(training_x_normalized, training_y, sample_weight=training_weights)

    if verbose:
        print(speech_detection)

    # save some memory
    del training_x_normalized
    del training_weights

    # find synchronization bias
    bias = find_sync_bias(speech_detection, training_x, training_y, training_meta, verbose=verbose)

    return [speech_detection, bias]

def predict(model, test_x, file_labels=None):
    speech_detection = model[0]
    test_x = features.normalize_by_file(test_x, normalize, file_labels)
    test_x = transform(test_x)
    return speech_detection.predict_proba(test_x)[:,1]

def serialize(model):
    import pickle
    return pickle.dumps(model)

def deserialize(data):
    import pickle
    return pickle.loads(data)

def load(model_file):
    with open(model_file, 'rb') as f:
        return deserialize(f.read())

def save(trained_model, target_file):
    with open(target_file, 'wb') as f:
        f.write(serialize(trained_model))
